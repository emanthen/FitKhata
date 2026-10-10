from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal

import pytest
from django.utils import timezone

from accounts.models import User
from billing.models import Payment
from coaching.models import TrainerCommission
from core.context import system_context
from gyms.models import Gym, Organization
from members.models import Member
from retention.models import RetentionCall
from staff.models import LeaveBalance, LeaveRequest, PayrollRun, Payslip, StaffShift
from staff.services import (
    InsufficientLeaveBalance,
    PayrollRunLocked,
    ShiftConflict,
    SlabsNotConfirmed,
    adjust_leave_balance,
    approve_leave_request,
    create_advance,
    create_payroll_run,
    create_shift,
    finalize_payroll_run,
    record_staff_checkins_batch,
    register_staff_profile,
    staff_leaderboard,
    submit_leave_request,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def gym():
    with system_context():
        org = Organization.objects.create(name="Staff Test Org")
        return Gym.objects.create(org=org, code="STF1", name="Staff Test Gym")


@pytest.fixture
def user(gym):
    with system_context():
        return User.objects.create_user(
            phone="+9779811000001", password="x", full_name="Test Staff"
        )


@pytest.fixture
def staff(gym, user):
    with system_context():
        return register_staff_profile(
            gym,
            user,
            employment_type="monthly",
            base_salary_npr=Decimal("30000.00"),
            joined_on=date(2026, 1, 1),
        )


def test_register_staff_profile_allocates_a_badge_code(gym, user):
    with system_context():
        profile = register_staff_profile(
            gym, user, employment_type="monthly", base_salary_npr=Decimal("1000"),
            joined_on=date(2026, 1, 1),
        )
    assert profile.badge_code == "STAFF-STF1-0001"
    assert bytes(profile.qr_secret)


def test_create_shift_rejects_overlap(staff):
    with system_context():
        create_shift(staff, date(2026, 10, 12), time(9, 0), time(17, 0))
        with pytest.raises(ShiftConflict):
            create_shift(staff, date(2026, 10, 12), time(16, 0), time(20, 0))


def test_create_shift_allows_touching_not_overlapping(staff):
    with system_context():
        create_shift(staff, date(2026, 10, 12), time(9, 0), time(13, 0))
        # Does not raise.
        create_shift(staff, date(2026, 10, 12), time(13, 0), time(17, 0))
        assert StaffShift.objects.filter(staff=staff).count() == 2


def test_badge_clock_in_then_clock_out_pairs(staff):
    with system_context():
        t1 = timezone.make_aware(datetime(2026, 10, 12, 9, 0))
        t2 = timezone.make_aware(datetime(2026, 10, 12, 17, 0))
        record_staff_checkins_batch([{"staff": staff, "scanned_at": t1}])
        attendance = staff.attendances.get()
        assert attendance.clock_in == t1
        assert attendance.clock_out is None

        record_staff_checkins_batch([{"staff": staff, "scanned_at": t2}])
        attendance.refresh_from_db()
        assert attendance.clock_out == t2
        assert staff.attendances.count() == 1


def test_badge_third_scan_opens_a_new_session(staff):
    with system_context():
        for hour in (9, 17, 18):
            record_staff_checkins_batch(
                [
                    {
                        "staff": staff,
                        "scanned_at": timezone.make_aware(datetime(2026, 10, 12, hour)),
                    }
                ]
            )
        assert staff.attendances.count() == 2


def test_badge_clock_in_flags_late_arrival_against_scheduled_shift(staff):
    with system_context():
        create_shift(staff, date(2026, 10, 12), time(9, 0), time(17, 0))
        on_time = record_staff_checkins_batch(
            [
                {
                    "staff": staff,
                    "scanned_at": timezone.make_aware(datetime(2026, 10, 12, 9, 5)),
                }
            ]
        )
        assert on_time["accepted"][0]["late"] is False

        # Close that session, then a late clock-in the next day.
        record_staff_checkins_batch(
            [{"staff": staff, "scanned_at": timezone.make_aware(datetime(2026, 10, 12, 17, 0))}]
        )
        create_shift(staff, date(2026, 10, 13), time(9, 0), time(17, 0))
        late = record_staff_checkins_batch(
            [
                {
                    "staff": staff,
                    "scanned_at": timezone.make_aware(datetime(2026, 10, 13, 9, 30)),
                }
            ]
        )
        assert late["accepted"][0]["late"] is True


def test_badge_clock_in_with_no_scheduled_shift_has_no_late_flag(staff):
    with system_context():
        result = record_staff_checkins_batch(
            [{"staff": staff, "scanned_at": timezone.make_aware(datetime(2026, 10, 12, 9, 0))}]
        )
        assert result["accepted"][0]["late"] is None


def test_approve_leave_request_decrements_balance(staff):
    with system_context():
        LeaveBalance.objects.create(
            org=staff.org, gym=staff.gym, staff=staff, kind="casual", days_available=Decimal("5")
        )
        leave = submit_leave_request(
            staff, from_date=date(2026, 10, 20), to_date=date(2026, 10, 21), kind="casual"
        )
        approve_leave_request(leave, actor=None)

        leave.refresh_from_db()
        balance = LeaveBalance.objects.get(staff=staff, kind="casual")
        assert leave.status == LeaveRequest.Status.APPROVED
        assert balance.days_available == Decimal("3")  # 5 - 2 days


def test_approve_leave_request_rejects_over_draw(staff):
    with system_context():
        LeaveBalance.objects.create(
            org=staff.org, gym=staff.gym, staff=staff, kind="casual", days_available=Decimal("1")
        )
        leave = submit_leave_request(
            staff, from_date=date(2026, 10, 20), to_date=date(2026, 10, 21), kind="casual"
        )
        with pytest.raises(InsufficientLeaveBalance):
            approve_leave_request(leave, actor=None)

        leave.refresh_from_db()
        assert leave.status == LeaveRequest.Status.PENDING


def test_adjust_leave_balance_credits_days(staff):
    with system_context():
        adjust_leave_balance(staff, "sick", Decimal("2"), actor=None)
        adjust_leave_balance(staff, "sick", Decimal("1"), actor=None)
        balance = LeaveBalance.objects.get(staff=staff, kind="sick")
        assert balance.days_available == Decimal("3")


def test_create_payroll_run_computes_one_payslip_per_active_staff(staff):
    with system_context():
        run = create_payroll_run(staff.gym, "2083-06")
        assert run.status == PayrollRun.Status.DRAFT
        payslip = Payslip.objects.get(run=run, staff=staff)
        assert payslip.base_npr == Decimal("30000.00")
        assert run.totals_npr == payslip.net_npr


def test_create_payroll_run_recompute_replaces_draft_payslips(staff):
    with system_context():
        create_advance(staff, Decimal("1000.00"), date(2026, 10, 1), actor=None)
        run = create_payroll_run(staff.gym, "2083-06")
        first_payslip_id = Payslip.objects.get(run=run, staff=staff).pk

        # Recomputing (still draft) replaces the payslip, not duplicates it.
        run = create_payroll_run(staff.gym, "2083-06")
        assert Payslip.objects.filter(run=run, staff=staff).count() == 1
        assert Payslip.objects.get(run=run, staff=staff).pk != first_payslip_id


def test_finalize_payroll_run_blocked_when_slabs_not_confirmed(staff):
    with system_context():
        run = create_payroll_run(staff.gym, "2083-06")
        with pytest.raises(SlabsNotConfirmed):
            finalize_payroll_run(run, actor=None)
        run.refresh_from_db()
        assert run.status == PayrollRun.Status.DRAFT


def test_create_payroll_run_refuses_on_a_finalized_run(staff, monkeypatch):
    from staff import services as staff_services

    monkeypatch.setattr(
        staff_services, "load_slabs", lambda fy: {"confirmed": True, "slabs": []}
    )
    with system_context():
        run = create_payroll_run(staff.gym, "2083-06")
        finalize_payroll_run(run, actor=None)
        with pytest.raises(PayrollRunLocked):
            create_payroll_run(staff.gym, "2083-06")
        run.refresh_from_db()
        assert run.status == PayrollRun.Status.FINALIZED


def test_staff_leaderboard_counts_sales_calls_and_saves(staff):
    with system_context():
        member = Member.objects.create(
            org=staff.org,
            gym=staff.gym,
            member_code="SAPI1-0001",
            full_name="Some Member",
            phone="+9779800000011",
            qr_secret=b"fixture-not-a-real-secret",
        )
        import uuid

        payment = Payment.objects.create(
            org=staff.org,
            gym=staff.gym,
            member=member,
            mode=Payment.Mode.CASH,
            channel=Payment.Channel.DESK,
            transaction_uuid=uuid.uuid4(),
            amount_npr=Decimal("3000.00"),
            status=Payment.Status.COMPLETED,
            collected_by=staff.user,
        )
        # created_at is auto_now_add — .create() ignores an explicit value,
        # so backdate it with a raw .update() (bypasses save()'s auto_now).
        Payment.objects.filter(pk=payment.pk).update(
            created_at=timezone.make_aware(datetime(2026, 9, 20))
        )
        RetentionCall.objects.create(
            org=staff.org,
            gym=staff.gym,
            member=member,
            queue_date=date(2026, 9, 18),
            assigned_to=staff.user,
            outcome=RetentionCall.Outcome.COMING_BACK,
            completed_at=timezone.make_aware(datetime(2026, 9, 19)),
        )

        rows = staff_leaderboard(staff.gym, "2083-06")
        row = next(r for r in rows if r["staff_id"] == staff.pk)
        assert row["renewals_sold"] == 1
        assert row["renewals_npr"] == Decimal("3000.00")
        assert row["calls_completed"] == 1
        assert row["saves"] == 1


def test_payroll_run_includes_trainer_commission(staff):
    with system_context():
        TrainerCommission.objects.create(
            org=staff.org,
            gym=staff.gym,
            trainer=staff.user,
            source=TrainerCommission.Source.PT_SESSION,
            amount_npr=Decimal("500.00"),
            period="2026-09",  # AD month inside BS 2083-06
        )
        run = create_payroll_run(staff.gym, "2083-06")
        payslip = Payslip.objects.get(run=run, staff=staff)
        assert payslip.commission_npr == Decimal("500.00")
