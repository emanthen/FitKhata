from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from django.db.models import Sum
from django.utils import timezone

from accounts.models import User
from billing.models import CashShift, Invoice, Payment
from core.context import system_context, tenant_context
from gyms.models import Gym, Organization
from members.models import Member, Membership, Plan
from reports import services
from reports.tasks import _refresh_all

pytestmark = pytest.mark.django_db


@pytest.fixture
def gym():
    with system_context():
        org = Organization.objects.create(name="Reports Test Org")
        return Gym.objects.create(org=org, code="RPT1", name="Reports Test Gym")


@pytest.fixture
def plan(gym):
    with system_context():
        return Plan.objects.create(
            org=gym.org, gym=gym, name="Monthly", duration_days=30, price_npr=Decimal("3000.00")
        )


@pytest.fixture
def staff_user(gym):
    with system_context():
        return User.objects.create_user(
            phone="+9779822000001", password="x", full_name="Desk Staff"
        )


def _make_member(gym: Gym, code: str = "RPT1-0001") -> Member:
    return Member.objects.create(
        org=gym.org,
        gym=gym,
        member_code=code,
        full_name="Test Member",
        phone=f"+97798{code[-4:]}00011",
        qr_secret=b"fixture-not-a-real-secret",
    )


def _make_completed_payment(gym, member, amount, mode, staff, day: date) -> Payment:
    payment = Payment.objects.create(
        org=gym.org,
        gym=gym,
        member=member,
        mode=mode,
        channel=Payment.Channel.DESK,
        transaction_uuid=uuid.uuid4(),
        amount_npr=amount,
        status=Payment.Status.COMPLETED,
        collected_by=staff,
    )
    # created_at is auto_now_add — backdate it with .update() (bypasses save()).
    Payment.objects.filter(pk=payment.pk).update(
        created_at=timezone.make_aware(datetime.combine(day, datetime.min.time()))
    )
    return payment


def test_revenue_trend_matches_raw_payment_sum(gym, staff_user):
    today = timezone.localdate()
    with system_context():
        member = _make_member(gym)
        _make_completed_payment(
            gym, member, Decimal("1000.00"), Payment.Mode.CASH, staff_user, today
        )
        _make_completed_payment(
            gym, member, Decimal("500.00"), Payment.Mode.ESEWA, staff_user, today
        )
        raw_total = Payment.objects.filter(gym=gym, status=Payment.Status.COMPLETED).aggregate(
            total=Sum("amount_npr")
        )["total"]

    # _refresh_all() handles its own system_context() internally (owns the
    # MVs + bypasses RLS on the source tables, see reports/tasks.py) — call
    # it outside the fixture-writing block above, then read through
    # tenant_context() below, matching the real request/Celery split.
    _refresh_all()

    with tenant_context([str(gym.pk)]):
        trend = services.revenue_trend(gym, today, today)

    assert len(trend) == 1
    assert trend[0]["amount_npr"] == raw_total == Decimal("1500.00")
    assert trend[0]["payment_count"] == 2


def test_dashboard_summary_revenue_today_matches_raw_sum(gym, staff_user):
    today = timezone.localdate()
    with system_context():
        member = _make_member(gym)
        _make_completed_payment(
            gym, member, Decimal("2000.00"), Payment.Mode.CASH, staff_user, today
        )

    _refresh_all()

    with tenant_context([str(gym.pk)]):
        summary = services.dashboard_summary(gym)
    assert summary["revenue_today_npr"] == Decimal("2000.00")
    assert summary["revenue_month_npr"] == Decimal("2000.00")
    assert summary["active_members"] == 0  # member created above has no ACTIVE status set


def test_membership_flow_classifies_new_then_renewed(gym, plan):
    with system_context():
        member = _make_member(gym)
        m1 = Membership.objects.create(
            org=gym.org,
            gym=gym,
            member=member,
            plan=plan,
            start_date=date(2026, 1, 1),
            expiry_date=date(2026, 1, 31),
            status=Membership.Status.EXPIRED,
        )
        Membership.objects.filter(pk=m1.pk).update(
            created_at=timezone.make_aware(datetime(2026, 1, 1))
        )
        m2 = Membership.objects.create(
            org=gym.org,
            gym=gym,
            member=member,
            plan=plan,
            start_date=date(2026, 2, 1),
            expiry_date=date(2026, 3, 3),
            status=Membership.Status.ACTIVE,
        )
        Membership.objects.filter(pk=m2.pk).update(
            created_at=timezone.make_aware(datetime(2026, 2, 1))
        )

    _refresh_all()

    with tenant_context([str(gym.pk)]):
        flow = services.membership_flow(gym, date(2026, 1, 1), date(2026, 2, 1))
    by_day = {row["day"]: row for row in flow}

    assert by_day[date(2026, 1, 1)]["new_count"] == 1
    assert by_day[date(2026, 1, 1)]["renewed_count"] == 0
    assert by_day[date(2026, 2, 1)]["renewed_count"] == 1
    assert by_day[date(2026, 2, 1)]["new_count"] == 0


def test_membership_flow_counts_expiry_on_expiry_date(gym, plan):
    with system_context():
        member = _make_member(gym)
        m = Membership.objects.create(
            org=gym.org,
            gym=gym,
            member=member,
            plan=plan,
            start_date=date(2026, 1, 1),
            expiry_date=date(2026, 1, 31),
            status=Membership.Status.EXPIRED,
        )
        Membership.objects.filter(pk=m.pk).update(
            created_at=timezone.make_aware(datetime(2026, 1, 1))
        )

    _refresh_all()

    with tenant_context([str(gym.pk)]):
        flow = services.membership_flow(gym, date(2026, 1, 31), date(2026, 1, 31))
    assert flow[0]["expired_count"] == 1


def test_membership_flow_churn_waits_for_grace_window(gym, plan):
    """An expired membership with no renewal only counts as churned once
    gym.settings["warning_days"] (default 7) have passed since expiry.
    """
    today = timezone.localdate()
    with system_context():
        member = _make_member(gym)
        recently_expired = today - timedelta(days=3)
        long_expired = today - timedelta(days=10)

        m_recent = Membership.objects.create(
            org=gym.org,
            gym=gym,
            member=member,
            plan=plan,
            start_date=recently_expired - timedelta(days=30),
            expiry_date=recently_expired,
            status=Membership.Status.EXPIRED,
        )
        Membership.objects.filter(pk=m_recent.pk).update(created_at=timezone.now())

        member2 = _make_member(gym, "RPT1-0002")
        m_long = Membership.objects.create(
            org=gym.org,
            gym=gym,
            member=member2,
            plan=plan,
            start_date=long_expired - timedelta(days=30),
            expiry_date=long_expired,
            status=Membership.Status.EXPIRED,
        )
        Membership.objects.filter(pk=m_long.pk).update(created_at=timezone.now())

    _refresh_all()

    with tenant_context([str(gym.pk)]):
        recent_flow = services.membership_flow(gym, recently_expired, recently_expired)
        long_flow = services.membership_flow(gym, long_expired, long_expired)

    assert recent_flow[0]["churned_count"] == 0
    assert long_flow[0]["churned_count"] == 1


def test_dues_ageing_buckets_by_bill_date(gym):
    today = timezone.localdate()
    with system_context():
        member = _make_member(gym)
        for days_ago, amount in [(5, "100.00"), (45, "200.00"), (90, "300.00")]:
            Invoice.objects.create(
                org=gym.org,
                gym=gym,
                number=f"INV-{days_ago}",
                fiscal_year=2083,
                status=Invoice.Status.DRAFT,
                member=member,
                subtotal_npr=Decimal(amount),
                total_npr=Decimal(amount),
                bill_date=today - timedelta(days=days_ago),
            )

        buckets = services.dues_ageing_report(gym, today=today)
        assert buckets["0-30"]["count"] == 1
        assert buckets["0-30"]["total_npr"] == Decimal("100.00")
        assert buckets["31-60"]["total_npr"] == Decimal("200.00")
        assert buckets["60+"]["total_npr"] == Decimal("300.00")


def test_vat_sales_register_reconciles_with_invoice_totals(gym):
    with system_context():
        member = _make_member(gym)
        for i in range(3):
            Invoice.objects.create(
                org=gym.org,
                gym=gym,
                number=f"2083-0000{i}",
                fiscal_year=2083,
                status=Invoice.Status.ISSUED,
                member=member,
                subtotal_npr=Decimal("1000.00"),
                taxable_npr=Decimal("1000.00"),
                vat_npr=Decimal("130.00"),
                total_npr=Decimal("1130.00"),
                bill_date=date(2026, 9, 1 + i),
                bill_date_bs="2083-06-01",
            )
        # A different fiscal year's invoice must not leak into the register.
        Invoice.objects.create(
            org=gym.org,
            gym=gym,
            number="2084-00001",
            fiscal_year=2084,
            status=Invoice.Status.ISSUED,
            member=member,
            subtotal_npr=Decimal("1.00"),
            vat_npr=Decimal("1.00"),
            total_npr=Decimal("1.00"),
            bill_date=date(2027, 9, 1),
            bill_date_bs="2084-06-01",
        )

        register = services.vat_sales_register(gym, 2083)
        raw_vat_total = Invoice.objects.filter(
            gym=gym, fiscal_year=2083, status=Invoice.Status.ISSUED
        ).aggregate(total=Sum("vat_npr"))["total"]

        assert len(register["rows"]) == 3
        register_vat_total = sum(
            (m["vat_npr"] for m in register["monthly_totals"].values()), Decimal("0.00")
        )
        assert register_vat_total == raw_vat_total == Decimal("390.00")


def test_cash_variance_for_day_sums_closed_shifts(gym, staff_user):
    today = timezone.localdate()
    with system_context():
        shift = CashShift.objects.create(
            org=gym.org,
            gym=gym,
            staff=staff_user,
            opening_float_npr=Decimal("1000.00"),
            counted_cash_npr=Decimal("1050.00"),
        )
        CashShift.objects.filter(pk=shift.pk).update(
            closed_at=timezone.make_aware(datetime.combine(today, datetime.min.time()))
        )

        variance_total = services.cash_variance_for_day(gym, today)
        assert variance_total == Decimal(
            "50.00"
        )  # no payments against this shift -> expected = opening float


def test_assemble_owner_summary_includes_red_list_count(gym):
    today = timezone.localdate()
    with system_context():
        member = _make_member(gym)
        member.risk_state = Member.RiskState.RED_LIST
        member.save(update_fields=["risk_state"])

    _refresh_all()

    with tenant_context([str(gym.pk)]):
        summary = services.assemble_owner_summary(gym, today)
    assert summary["red_list_count"] == 1
    assert summary["new_count"] == 0
