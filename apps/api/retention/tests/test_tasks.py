from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from accounts.models import StaffRole, User
from core.context import system_context
from gyms.models import Gym, Organization
from members.models import Member, Membership, Plan
from members.services import register_member, sell_membership
from notifications.models import Notification, SmsWallet
from retention.models import RetentionCall
from retention.tasks import (
    build_call_queue,
    churn_engine,
    expire_memberships,
    notify_risk_transitions,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def gym():
    with system_context():
        org = Organization.objects.create(name="Retention Task Test Org")
        return Gym.objects.create(org=org, code="RTT1", name="Retention Task Test Gym")


# --- expire_memberships -----------------------------------------------------


def test_expire_memberships_flips_membership_and_member_status(gym):
    with system_context():
        plan = Plan.objects.create(
            org=gym.org, gym=gym, name="Monthly", duration_days=30, price_npr=Decimal("3000")
        )
        member = register_member(gym, full_name="Ram Shrestha", phone="+9779800000001")
        membership = sell_membership(member, plan, today=date(2020, 1, 1))  # long expired

    expire_memberships()

    with system_context():
        membership.refresh_from_db()
        member.refresh_from_db()
    assert membership.status == Membership.Status.EXPIRED
    assert member.status == Member.Status.EXPIRED


def test_expire_memberships_leaves_active_memberships_alone(gym):
    with system_context():
        plan = Plan.objects.create(
            org=gym.org, gym=gym, name="Monthly", duration_days=30, price_npr=Decimal("3000")
        )
        member = register_member(gym, full_name="Hari Tamang", phone="+9779800000002")
        membership = sell_membership(member, plan, today=date.today())

    expire_memberships()

    with system_context():
        membership.refresh_from_db()
    assert membership.status == Membership.Status.ACTIVE


# --- build_call_queue: round-robin never assigns to inactive staff ----------


def test_build_call_queue_never_assigns_to_inactive_staff(gym):
    with system_context():
        active_1 = User.objects.create_user(phone="+9779811111111", password="x")
        StaffRole.objects.create(
            user=active_1, org=gym.org, gym=gym, role=StaffRole.Role.FRONT_DESK, is_active=True
        )
        active_2 = User.objects.create_user(phone="+9779822222222", password="x")
        StaffRole.objects.create(
            user=active_2, org=gym.org, gym=gym, role=StaffRole.Role.FRONT_DESK, is_active=True
        )
        inactive = User.objects.create_user(phone="+9779833333333", password="x")
        StaffRole.objects.create(
            user=inactive, org=gym.org, gym=gym, role=StaffRole.Role.FRONT_DESK, is_active=False
        )

        for i in range(10):
            Member.objects.create(
                org=gym.org,
                gym=gym,
                member_code=f"RTT1-{i:04d}",
                full_name=f"Member {i}",
                phone=f"+97798000001{i:02d}",
                qr_secret=b"fixture-not-a-real-secret",
                risk_state=Member.RiskState.RED_LIST,
            )

    build_call_queue()

    with system_context():
        assigned_ids = set(
            RetentionCall.objects.filter(gym=gym).values_list("assigned_to_id", flat=True)
        )
    assert inactive.pk not in assigned_ids
    assert assigned_ids <= {active_1.pk, active_2.pk}
    assert len(assigned_ids) == 2  # round-robin actually used both


def test_build_call_queue_skips_members_queued_in_the_last_3_days(gym):
    with system_context():
        staff = User.objects.create_user(phone="+9779844444444", password="x")
        StaffRole.objects.create(
            user=staff, org=gym.org, gym=gym, role=StaffRole.Role.FRONT_DESK, is_active=True
        )
        member = Member.objects.create(
            org=gym.org,
            gym=gym,
            member_code="RTT1-0001",
            full_name="Already Queued",
            phone="+9779855555555",
            qr_secret=b"fixture-not-a-real-secret",
            risk_state=Member.RiskState.RED_LIST,
        )
        RetentionCall.objects.create(
            org=gym.org, gym=gym, member=member, queue_date=date.today() - timedelta(days=1)
        )

    build_call_queue()

    with system_context():
        count = RetentionCall.objects.filter(gym=gym, member=member).count()
    assert count == 1  # no second row queued today


# --- churn_engine: risk transitions driven by last_check_in_at -------------


def test_churn_engine_promotes_a_long_absent_member_to_red_list(gym):
    today = timezone.now()
    with system_context():
        member = Member.objects.create(
            org=gym.org,
            gym=gym,
            member_code="RTT1-0002",
            full_name="Long Absent",
            phone="+9779866666666",
            qr_secret=b"fixture-not-a-real-secret",
            last_check_in_at=today - timedelta(days=20),
        )

    churn_engine()

    with system_context():
        member.refresh_from_db()
    assert member.risk_state == Member.RiskState.RED_LIST  # gym default red_list_days=10
    assert member.churn_score > 0


def test_churn_engine_writes_a_risk_state_change_row(gym):
    today = timezone.now()
    with system_context():
        member = Member.objects.create(
            org=gym.org,
            gym=gym,
            member_code="RTT1-0003",
            full_name="Newly Absent",
            phone="+9779877777777",
            qr_secret=b"fixture-not-a-real-secret",
            last_check_in_at=today - timedelta(days=20),
        )

    churn_engine()

    from retention.models import RiskStateChange

    with system_context():
        change = RiskStateChange.objects.get(member=member)
    assert change.from_state == Member.RiskState.NORMAL
    assert change.to_state == Member.RiskState.RED_LIST


def test_churn_engine_leaves_recently_active_members_normal(gym):
    with system_context():
        member = Member.objects.create(
            org=gym.org,
            gym=gym,
            member_code="RTT1-0004",
            full_name="Recently Active",
            phone="+9779888888888",
            qr_secret=b"fixture-not-a-real-secret",
            last_check_in_at=timezone.now(),
        )

    churn_engine()

    with system_context():
        member.refresh_from_db()
    assert member.risk_state == Member.RiskState.NORMAL


# --- notify_risk_transitions: deliberately decoupled from churn_engine -----


def test_notify_risk_transitions_reaches_notify_for_warning_and_red_list(gym):
    with system_context():
        SmsWallet.objects.create(org=gym.org, balance_npr=Decimal("1000.00"))
        warning_member = Member.objects.create(
            org=gym.org,
            gym=gym,
            member_code="RTT1-0005",
            full_name="Warning Member",
            phone="+9779899999901",
            qr_secret=b"fixture-not-a-real-secret",
            last_check_in_at=timezone.now() - timedelta(days=8),
        )
        red_list_member = Member.objects.create(
            org=gym.org,
            gym=gym,
            member_code="RTT1-0006",
            full_name="Red List Member",
            phone="+9779899999902",
            qr_secret=b"fixture-not-a-real-secret",
            last_check_in_at=timezone.now() - timedelta(days=20),
        )

    churn_engine()  # writes today's RiskStateChange rows
    notify_risk_transitions()

    with system_context():
        assert Notification.objects.filter(
            member=warning_member, template_key="red_list_day7"
        ).exists()
        assert Notification.objects.filter(
            member=red_list_member, template_key="red_list_day10"
        ).exists()


def test_notify_risk_transitions_does_not_notify_members_still_normal(gym):
    with system_context():
        member = Member.objects.create(
            org=gym.org,
            gym=gym,
            member_code="RTT1-0007",
            full_name="Still Normal",
            phone="+9779899999903",
            qr_secret=b"fixture-not-a-real-secret",
            last_check_in_at=timezone.now(),
        )

    churn_engine()
    notify_risk_transitions()

    with system_context():
        assert not Notification.objects.filter(
            member=member, template_key__in=["red_list_day7", "red_list_day10"]
        ).exists()
