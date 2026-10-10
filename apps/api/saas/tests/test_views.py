"""HTTP-level: the read_only write-block (core.middleware.TenantMiddleware)
and IsPlatformStaff. Exercised through a real APIClient so routing/
middleware/permissions are all actually hit, not just the service layer.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from django_otp.plugins.otp_totp.models import TOTPDevice
from rest_framework.test import APIClient

from accounts.models import StaffRole, User
from accounts.tokens import issue_tokens_for_user
from core.context import system_context
from gyms.models import Gym, Organization
from saas.models import SaasPlan, Subscription

pytestmark = pytest.mark.django_db


def _client_for(user: User, gym: Gym | None = None) -> APIClient:
    tokens = issue_tokens_for_user(user)
    client = APIClient()
    headers = {"HTTP_AUTHORIZATION": f"Bearer {tokens['access']}"}
    if gym is not None:
        headers["HTTP_X_GYM_ID"] = str(gym.pk)
    client.credentials(**headers)
    return client


@pytest.fixture
def gym_with_owner():
    with system_context():
        org = Organization.objects.create(name="Saas View Test Org")
        gym = Gym.objects.create(org=org, code="SVT1", name="Saas View Test Gym")
        user = User.objects.create_user(phone="+9779822000066", password="x", full_name="Owner")
        StaffRole.objects.create(org=org, gym=None, user=user, role=StaffRole.Role.OWNER)
        return gym, user


def _subscribe(gym, status):
    with system_context():
        plan = SaasPlan.objects.get(code=SaasPlan.Code.STARTER)
        Subscription.objects.create(
            org=gym.org,
            plan=plan,
            billing_cycle=Subscription.BillingCycle.MONTHLY,
            current_period_start=date.today(),
            current_period_end=date.today() + timedelta(days=30),
            status=status,
        )


def test_read_only_subscription_blocks_member_create(gym_with_owner):
    gym, user = gym_with_owner
    _subscribe(gym, Subscription.Status.READ_ONLY)
    client = _client_for(user, gym)

    response = client.post(
        "/api/v1/members/", {"full_name": "Blocked Member", "phone": "+9779800099001"}
    )

    assert response.status_code == 402


def test_active_subscription_allows_member_create(gym_with_owner):
    gym, user = gym_with_owner
    _subscribe(gym, Subscription.Status.ACTIVE)
    client = _client_for(user, gym)

    response = client.post(
        "/api/v1/members/", {"full_name": "Allowed Member", "phone": "+9779800099002"}
    )

    assert response.status_code == 201


def test_read_only_still_allows_attendance_manual_checkin(gym_with_owner):
    gym, user = gym_with_owner
    _subscribe(gym, Subscription.Status.READ_ONLY)
    client = _client_for(user, gym)

    response = client.post("/api/v1/attendance/manual", {})

    # 400/404 (missing member_code etc.) proves the view itself ran, i.e.
    # the middleware did NOT short-circuit with 402 — that's what this
    # test is checking, not the manual-checkin validation logic itself.
    assert response.status_code != 402


def test_read_only_still_allows_get_requests(gym_with_owner):
    gym, user = gym_with_owner
    _subscribe(gym, Subscription.Status.READ_ONLY)
    client = _client_for(user, gym)

    response = client.get("/api/v1/members/")

    assert response.status_code == 200


def test_is_platform_staff_rejects_non_staff_user(gym_with_owner):
    _, user = gym_with_owner  # a gym owner, not platform staff
    client = _client_for(user)

    response = client.get("/api/v1/platform/tenants")

    assert response.status_code == 403


def test_is_platform_staff_rejects_staff_without_totp():
    with system_context():
        staff_user = User.objects.create_user(
            phone="+9779811000010", password="x", full_name="No TOTP Staff", is_staff=True
        )
    client = _client_for(staff_user)

    response = client.get("/api/v1/platform/tenants")

    assert response.status_code == 403


def test_is_platform_staff_allows_staff_with_confirmed_totp():
    with system_context():
        staff_user = User.objects.create_user(
            phone="+9779811000011", password="x", full_name="Confirmed Staff", is_staff=True
        )
        TOTPDevice.objects.create(user=staff_user, name="default", confirmed=True)
    client = _client_for(staff_user)

    response = client.get("/api/v1/platform/tenants")

    assert response.status_code == 200
