from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from accounts.models import StaffRole, User
from accounts.tokens import issue_tokens_for_user
from core.context import system_context
from gyms.models import Gym, Organization
from staff.services import register_staff_profile

pytestmark = pytest.mark.django_db


def _client_for(user: User, gym: Gym) -> APIClient:
    tokens = issue_tokens_for_user(user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}", HTTP_X_GYM_ID=str(gym.pk))
    return client


@pytest.fixture
def setup():
    with system_context():
        org = Organization.objects.create(name="Staff API Test Org")
        gym = Gym.objects.create(org=org, code="SAPI1", name="Staff API Test Gym")
        owner = User.objects.create_user(phone="+9774100000001", password="x")
        StaffRole.objects.create(user=owner, org=org, gym=gym, role=StaffRole.Role.OWNER)
        manager = User.objects.create_user(phone="+9774100000002", password="x")
        StaffRole.objects.create(user=manager, org=org, gym=gym, role=StaffRole.Role.MANAGER)
        staff_user = User.objects.create_user(
            phone="+9774100000003", password="x", full_name="Employee One"
        )
        profile = register_staff_profile(
            gym,
            staff_user,
            employment_type="monthly",
            base_salary_npr=Decimal("25000.00"),
            pan_no="PAN123456",
            joined_on=date(2026, 1, 1),
        )
    return org, gym, owner, manager, profile


def test_owner_sees_decrypted_bank_account_and_pan(setup):
    _org, gym, owner, _manager, profile = setup
    client = _client_for(owner, gym)

    response = client.patch(
        f"/api/v1/staff-profiles/{profile.pk}/",
        {"bank_account_input": "1234567890", "bank_name": "Himalayan Bank"},
        format="json",
    )
    assert response.status_code == 200, response.content
    assert response.json()["bank_account"] == "1234567890"
    assert response.json()["pan_no"] == "PAN123456"


def test_manager_never_sees_bank_account_or_pan(setup):
    _org, gym, _owner, manager, profile = setup
    client = _client_for(manager, gym)

    response = client.get(f"/api/v1/staff-profiles/{profile.pk}/")
    assert response.status_code == 200, response.content
    body = response.json()
    assert body["bank_account"] is None
    assert body["pan_no"] is None


def test_front_desk_cannot_read_staff_profiles(setup):
    _org, gym, _owner, _manager, profile = setup
    front_desk = User.objects.create_user(phone="+9774100000009", password="x")
    with system_context():
        StaffRole.objects.create(
            user=front_desk, org=_org, gym=gym, role=StaffRole.Role.FRONT_DESK
        )
    client = _client_for(front_desk, gym)

    response = client.get(f"/api/v1/staff-profiles/{profile.pk}/")
    assert response.status_code == 403


def test_manager_can_create_a_payroll_run_but_cannot_finalize(setup):
    _org, gym, _owner, manager, _profile = setup
    client = _client_for(manager, gym)

    response = client.post("/api/v1/payroll-runs/", {"period_bs": "2083-06"}, format="json")
    assert response.status_code == 201, response.content
    run_id = response.json()["id"]

    finalize_response = client.post(f"/api/v1/payroll-runs/{run_id}/finalize/")
    assert finalize_response.status_code == 403


def test_owner_finalize_blocked_until_slabs_confirmed(setup):
    _org, gym, owner, _manager, _profile = setup
    client = _client_for(owner, gym)

    create_response = client.post("/api/v1/payroll-runs/", {"period_bs": "2083-06"}, format="json")
    run_id = create_response.json()["id"]

    finalize_response = client.post(f"/api/v1/payroll-runs/{run_id}/finalize/")
    assert finalize_response.status_code == 400
    assert "confirmed" in finalize_response.json()["detail"].lower()


def test_staff_shift_conflict_returns_400_not_500(setup):
    _org, gym, _owner, manager, profile = setup
    client = _client_for(manager, gym)

    first = client.post(
        "/api/v1/staff-shifts/",
        {"staff": str(profile.pk), "date": "2026-10-12", "start": "09:00", "end": "17:00"},
        format="json",
    )
    assert first.status_code == 201, first.content

    second = client.post(
        "/api/v1/staff-shifts/",
        {"staff": str(profile.pk), "date": "2026-10-12", "start": "16:00", "end": "20:00"},
        format="json",
    )
    assert second.status_code == 400
    assert "conflicting_shift_id" in second.json()
