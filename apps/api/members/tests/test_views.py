"""HTTP-level tests through DRF's APIClient — same reasoning as
accounts/tests/test_views.py: exercises routing/permissions/serializers
together, not just the service functions directly.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from accounts.models import StaffRole, User
from accounts.tokens import issue_tokens_for_user
from core.context import system_context
from gyms.models import Gym, Organization
from members.models import Plan

pytestmark = pytest.mark.django_db


def _client_for(user: User, gym: Gym) -> APIClient:
    tokens = issue_tokens_for_user(user)
    client = APIClient()
    client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {tokens['access']}", HTTP_X_GYM_ID=str(gym.pk)
    )
    return client


@pytest.fixture
def owner_setup():
    with system_context():
        org = Organization.objects.create(name="API Test Org")
        gym = Gym.objects.create(org=org, code="APIT1", name="API Test Gym")
        user = User.objects.create_user(phone="+9773000000001", password="x")
        StaffRole.objects.create(user=user, org=org, gym=gym, role=StaffRole.Role.OWNER)
        plan = Plan.objects.create(
            org=org, gym=gym, name="Monthly", duration_days=30, price_npr=Decimal("3000.00")
        )
    return org, gym, user, plan


@pytest.fixture
def front_desk_setup(owner_setup):
    org, gym, _owner, plan = owner_setup
    with system_context():
        user = User.objects.create_user(phone="+9773000000002", password="x")
        StaffRole.objects.create(user=user, org=org, gym=gym, role=StaffRole.Role.FRONT_DESK)
    return org, gym, user, plan


def test_register_member_via_api(owner_setup):
    _org, gym, owner, _plan = owner_setup
    client = _client_for(owner, gym)

    response = client.post(
        "/api/v1/members/",
        {"full_name": "Hari Thapa", "phone": "+9779811112222"},
        format="json",
    )

    assert response.status_code == 201, response.content
    body = response.json()
    assert body["member_code"] == "APIT1-0001"
    assert "qr_secret" not in body


def test_front_desk_can_register_members(front_desk_setup):
    _org, gym, user, _plan = front_desk_setup
    client = _client_for(user, gym)

    response = client.post(
        "/api/v1/members/", {"full_name": "Gita Rai", "phone": "+9779811113333"}, format="json"
    )
    assert response.status_code == 201, response.content


def test_front_desk_cannot_write_plans(front_desk_setup):
    _org, gym, user, _plan = front_desk_setup
    client = _client_for(user, gym)

    response = client.post(
        "/api/v1/plans/",
        {"name": "New Plan", "duration_days": 10, "price_npr": "500.00"},
        format="json",
    )
    assert response.status_code == 403


def test_search_finds_member_by_partial_name(owner_setup):
    _org, gym, owner, _plan = owner_setup
    client = _client_for(owner, gym)
    client.post(
        "/api/v1/members/",
        {"full_name": "Suresh Bastola", "phone": "+9779811114444"},
        format="json",
    )

    response = client.get("/api/v1/members/", {"q": "Sures"})

    assert response.status_code == 200
    names = [m["full_name"] for m in response.json()]
    assert "Suresh Bastola" in names


def test_sell_membership_action_creates_membership(owner_setup):
    _org, gym, owner, plan = owner_setup
    client = _client_for(owner, gym)
    register_resp = client.post(
        "/api/v1/members/", {"full_name": "Hari Thapa", "phone": "+9779811112222"}, format="json"
    )
    member_id = register_resp.json()["id"]

    response = client.post(f"/api/v1/members/{member_id}/sell/", {"plan_id": plan.pk})

    assert response.status_code == 201, response.content
    body = response.json()
    assert body["status"] == "active"
    assert body["start_date"] == date.today().isoformat()


def test_transfer_moves_member_to_target_gym(owner_setup):
    org, gym, owner, _plan = owner_setup
    with system_context():
        other_gym = Gym.objects.create(org=org, code="APIT2", name="Other Branch")

    client = _client_for(owner, gym)
    register_resp = client.post(
        "/api/v1/members/", {"full_name": "Hari Thapa", "phone": "+9779811112222"}, format="json"
    )
    member_id = register_resp.json()["id"]

    response = client.post(
        f"/api/v1/members/{member_id}/transfer/", {"gym_id": str(other_gym.pk)}, format="json"
    )

    assert response.status_code == 200, response.content

    with system_context():
        from members.models import Member

        assert Member.objects.get(pk=member_id).gym_id == other_gym.pk


def test_transfer_to_other_org_gym_returns_400_not_500(owner_setup):
    org, gym, owner, _plan = owner_setup
    with system_context():
        other_org = Organization.objects.create(name="Other Org")
        other_org_gym = Gym.objects.create(org=other_org, code="APIT3", name="Other Org Gym")

    client = _client_for(owner, gym)
    register_resp = client.post(
        "/api/v1/members/", {"full_name": "Hari Thapa", "phone": "+9779811112223"}, format="json"
    )
    member_id = register_resp.json()["id"]

    response = client.post(
        f"/api/v1/members/{member_id}/transfer/", {"gym_id": str(other_org_gym.pk)}, format="json"
    )

    assert response.status_code == 400, response.content


def test_missing_gym_header_is_forbidden_not_empty_list(owner_setup):
    """No X-Gym-Id means request.role is None (core/middleware.py), and
    every permission class here requires a role — same gate as every other
    tenant resource, not special-cased for members.
    """
    _org, _gym, owner, _plan = owner_setup
    tokens = issue_tokens_for_user(owner)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

    response = client.get("/api/v1/members/")

    assert response.status_code == 403


def test_waiver_upload_via_api(owner_setup):
    _org, gym, owner, _plan = owner_setup
    client = _client_for(owner, gym)
    register_resp = client.post(
        "/api/v1/members/", {"full_name": "Hari Thapa", "phone": "+9779811112222"}, format="json"
    )
    member_id = register_resp.json()["id"]

    fake_pdf = SimpleUploadedFile("waiver.pdf", b"%PDF-1.4 fake", content_type="application/pdf")
    response = client.post(
        "/api/v1/waivers/", {"member": member_id, "signed_pdf": fake_pdf}, format="multipart"
    )

    assert response.status_code == 201, response.content
    assert response.json()["member"] == member_id
