from __future__ import annotations

from datetime import date, timedelta

import pytest

from accounts.models import StaffRole, User
from core.context import system_context, tenant_context
from gyms.models import Gym, Organization
from saas.models import FeatureFlag, PlatformAuditLog, SaasPlan, Subscription
from saas.services import (
    MemberLimitExceeded,
    check_member_limit,
    has_feature,
    start_impersonation,
    start_trial,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def gym():
    with system_context():
        org = Organization.objects.create(name="Saas Services Test Org")
        return Gym.objects.create(org=org, code="SST1", name="Saas Services Test Gym")


@pytest.fixture
def owner(gym):
    with system_context():
        user = User.objects.create_user(
            phone="+9779822000055", password="x", full_name="Test Owner", email="owner@test.local"
        )
        StaffRole.objects.create(org=gym.org, gym=None, user=user, role=StaffRole.Role.OWNER)
        return user


def _subscribe(gym, plan_code=SaasPlan.Code.STARTER, status=Subscription.Status.ACTIVE):
    with system_context():
        plan = SaasPlan.objects.get(code=plan_code)
        return Subscription.objects.create(
            org=gym.org,
            plan=plan,
            billing_cycle=Subscription.BillingCycle.MONTHLY,
            current_period_start=date.today(),
            current_period_end=date.today() + timedelta(days=30),
            status=status,
        )


def test_start_trial_creates_trial_subscription(gym):
    with system_context():
        sub = start_trial(gym.org)
    assert sub.status == Subscription.Status.TRIAL
    assert sub.plan.code == SaasPlan.Code.STARTER
    assert sub.current_period_end - sub.current_period_start == timedelta(days=14)


def test_check_member_limit_allows_when_no_subscription(gym):
    check_member_limit(gym)  # no Subscription at all -> no-op, never raises


def test_check_member_limit_raises_at_boundary(gym):
    with system_context():
        plan = SaasPlan.objects.get(code=SaasPlan.Code.STARTER)
        plan.member_limit = 2
        plan.save(update_fields=["member_limit"])
        _subscribe(gym, SaasPlan.Code.STARTER)
        from members.services import register_member

        register_member(gym, full_name="A", phone="+9779800000011")
        register_member(gym, full_name="B", phone="+9779800000012")
        with pytest.raises(MemberLimitExceeded):
            check_member_limit(gym)


def test_check_member_limit_unlimited_for_enterprise(gym):
    with system_context():
        _subscribe(gym, SaasPlan.Code.ENTERPRISE)
    check_member_limit(gym)  # member_limit=None -> never raises


def test_has_feature_defaults_open_when_undeclared(gym):
    assert has_feature(gym.org, "some_never_configured_key") is True


def test_has_feature_plan_level_gate(gym):
    with system_context():
        plan = SaasPlan.objects.get(code=SaasPlan.Code.STARTER)
        plan.features = {"red_list": False}
        plan.save(update_fields=["features"])
        _subscribe(gym, SaasPlan.Code.STARTER)

    # has_feature()'s real callers (saas.decorators.requires_feature) only
    # ever run during request dispatch, inside TenantMiddleware's already-
    # scoped transaction — mirror that here rather than calling it with no
    # gym in scope at all, which the Subscription lookup it falls through
    # to needs (core/migrations/0004_platform_org_rls.py).
    with tenant_context([str(gym.pk)]):
        assert has_feature(gym.org, "red_list") is False


def test_has_feature_per_org_override_wins_over_plan(gym):
    with system_context():
        plan = SaasPlan.objects.get(code=SaasPlan.Code.STARTER)
        plan.features = {"red_list": False}
        plan.save(update_fields=["features"])
        _subscribe(gym, SaasPlan.Code.STARTER)
        FeatureFlag.objects.create(
            key="red_list", default=False, per_org_overrides={str(gym.org_id): True}
        )
    assert has_feature(gym.org, "red_list") is True


def test_has_feature_flag_default_used_when_no_plan_entry(gym):
    with system_context():
        FeatureFlag.objects.create(key="beta_thing", default=False)
    assert has_feature(gym.org, "beta_thing") is False


def test_start_impersonation_writes_audit_row_with_reason(gym, owner):
    platform_user = User.objects.create_user(
        phone="+9779811000001", password="x", full_name="Platform Staff", is_staff=True
    )
    with system_context():
        result = start_impersonation(platform_user, gym.org, "investigating a billing issue")

        assert "access" in result
        log = PlatformAuditLog.objects.get(
            org=gym.org, action="impersonation_started", actor=platform_user
        )
        assert log.reason == "investigating a billing issue"


def test_start_impersonation_raises_without_owner(gym):
    platform_user = User.objects.create_user(
        phone="+9779811000002", password="x", full_name="Platform Staff", is_staff=True
    )
    with pytest.raises(ValueError):
        with system_context():
            start_impersonation(platform_user, gym.org, "no owner here")
