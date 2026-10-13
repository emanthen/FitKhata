"""IDOR regression coverage for the HTTP layer — a different concern from
tests/rls/test_isolation.py (which proves the ORM/raw-SQL layer can't read
cross-tenant rows at all). Here: a *view* that fetches a specific object by
a client-supplied id must 404 for the wrong tenant's id, not leak a 403/500
or (worse) the object itself.

Not a fully automatic URL-conf-introspecting generator — docs/security/
AUDIT-2026-10-11.md already manually reviewed every raw-pk
get_object_or_404 call site in apps/api and judged each either gym/org-
filtered already, signed-token-scoped (member_id comes from
django.core.signing.loads, never a client-supplied path/body param), a
global catalog (e.g. Exercise), or platform-staff-gated. These tests cover
the real, reachable-by-a-regular-tenant-user endpoints as regression
coverage, not a search for new findings.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from django_otp.plugins.otp_totp.models import TOTPDevice
from rest_framework.test import APIClient

from accounts.models import StaffRole, User
from accounts.tokens import issue_tokens_for_user
from core.context import system_context
from gyms.models import Gym, Organization
from members.models import Member, Plan
from members.services import sell_membership
from publicapi.services import create_api_key, create_webhook_subscription
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
def two_gyms():
    """Two fully separate orgs/gyms/owners — gym_b's data is what gym_a's
    owner must never be able to reach by id.
    """
    with system_context():
        org_a = Organization.objects.create(name="IDOR Org A")
        org_b = Organization.objects.create(name="IDOR Org B")
        gym_a = Gym.objects.create(org=org_a, code="IDA1", name="IDOR Gym A")
        gym_b = Gym.objects.create(org=org_b, code="IDB1", name="IDOR Gym B")
        owner_a = User.objects.create_user(phone="+9771100000001", password="x")
        owner_b = User.objects.create_user(phone="+9771100000002", password="x")
        StaffRole.objects.create(user=owner_a, org=org_a, gym=gym_a, role=StaffRole.Role.OWNER)
        StaffRole.objects.create(user=owner_b, org=org_b, gym=gym_b, role=StaffRole.Role.OWNER)
    return {
        "org_a": org_a,
        "org_b": org_b,
        "gym_a": gym_a,
        "gym_b": gym_b,
        "owner_a": owner_a,
        "owner_b": owner_b,
    }


def test_member_detail_404s_for_the_wrong_gym(two_gyms):
    with system_context():
        member_b = Member.objects.create(
            org=two_gyms["org_b"],
            gym=two_gyms["gym_b"],
            member_code="IDB1-0001",
            full_name="Gym B Member",
            phone="+9779800000001",
            qr_secret=b"fixture-not-a-real-secret",
        )

    client = _client_for(two_gyms["owner_a"], two_gyms["gym_a"])
    response = client.get(f"/api/v1/members/{member_b.pk}/")

    assert response.status_code == 404


def test_invoice_detail_404s_for_the_wrong_gym(two_gyms):
    with system_context():
        member_b = Member.objects.create(
            org=two_gyms["org_b"],
            gym=two_gyms["gym_b"],
            member_code="IDB1-0002",
            full_name="Gym B Member 2",
            phone="+9779800000002",
            qr_secret=b"fixture-not-a-real-secret",
        )
        plan_b = Plan.objects.create(
            org=two_gyms["org_b"],
            gym=two_gyms["gym_b"],
            name="Monthly",
            duration_days=30,
            price_npr=Decimal("3000.00"),
        )
        membership_b = sell_membership(member_b, plan_b, today=date(2026, 1, 1))
        invoice_id = membership_b.invoice_id

    client = _client_for(two_gyms["owner_a"], two_gyms["gym_a"])
    response = client.get(f"/api/v1/invoices/{invoice_id}/")

    assert response.status_code == 404


def _give_enterprise_plan(org):
    """publicapi's integration endpoints are Enterprise-gated
    (publicapi/migrations/0002_gate_to_enterprise.py's FeatureFlag) —
    unrelated to the IDOR check itself, just what's needed to reach it.
    """
    with system_context():
        plan = SaasPlan.objects.get(code=SaasPlan.Code.ENTERPRISE)
        Subscription.objects.create(
            org=org,
            plan=plan,
            billing_cycle=Subscription.BillingCycle.MONTHLY,
            current_period_start=date(2026, 1, 1),
            current_period_end=date(2026, 1, 31),
        )


def test_api_key_revoke_404s_for_the_wrong_org(two_gyms):
    _give_enterprise_plan(two_gyms["org_a"])
    with system_context():
        api_key_b, _raw = create_api_key(two_gyms["org_b"], "Org B integration", ["members:read"])

    client = _client_for(two_gyms["owner_a"], two_gyms["gym_a"])
    response = client.post(f"/api/v1/integrations/api-keys/{api_key_b.pk}/revoke")

    assert response.status_code == 404
    with system_context():
        api_key_b.refresh_from_db()
        assert api_key_b.revoked_at is None


def test_webhook_deliveries_404s_for_the_wrong_org(two_gyms):
    _give_enterprise_plan(two_gyms["org_a"])
    with system_context():
        subscription_b = create_webhook_subscription(
            two_gyms["org_b"], "https://example.com/hook", ["member.created"], "secret"
        )

    client = _client_for(two_gyms["owner_a"], two_gyms["gym_a"])
    response = client.get(f"/api/v1/integrations/webhooks/{subscription_b.pk}/deliveries")

    assert response.status_code == 404


def test_platform_mark_paid_bank_requires_platform_staff_not_just_any_owner(two_gyms):
    """Not gym-scoped by design (FR-11.3: FitKhata staff manually confirm
    ANY org's bank transfer) — isolation here is IsPlatformStaff, not a
    queryset filter. A regular org owner (even a legitimate one, just not
    platform staff) must still be denied.
    """
    client = _client_for(two_gyms["owner_a"], two_gyms["gym_a"])

    response = client.post("/api/v1/platform/saas-invoices/1/mark-paid-bank")

    assert response.status_code == 403


def test_platform_mark_paid_bank_404s_for_a_nonexistent_invoice_even_for_platform_staff(two_gyms):
    with system_context():
        staff_user = User.objects.create_user(
            phone="+9771100000099", password="x", is_staff=True
        )
        TOTPDevice.objects.create(user=staff_user, name="default", confirmed=True)

    client = _client_for(staff_user)
    nonexistent_id = 999_999

    response = client.post(f"/api/v1/platform/saas-invoices/{nonexistent_id}/mark-paid-bank")

    assert response.status_code == 404
