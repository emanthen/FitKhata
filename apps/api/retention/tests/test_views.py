"""HTTP-level tests through DRF's APIClient -- same reasoning as
billing/tests/test_views.py: exercises routing/permissions/serializers
together, not just the service functions directly.
"""

from __future__ import annotations

from datetime import date

import pytest
from rest_framework.test import APIClient

from accounts.models import StaffRole, User
from accounts.tokens import issue_tokens_for_user
from core.context import system_context
from gyms.models import Gym, Organization
from members.models import Member
from retention.models import RetentionCall

pytestmark = pytest.mark.django_db


def _client_for(user: User, gym: Gym) -> APIClient:
    tokens = issue_tokens_for_user(user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}", HTTP_X_GYM_ID=str(gym.pk))
    return client


@pytest.fixture
def setup():
    with system_context():
        org = Organization.objects.create(name="Retention API Test Org")
        gym = Gym.objects.create(org=org, code="RAPI1", name="Retention API Test Gym")
        front_desk = User.objects.create_user(phone="+9774100000001", password="x")
        StaffRole.objects.create(user=front_desk, org=org, gym=gym, role=StaffRole.Role.FRONT_DESK)
        member = Member.objects.create(
            org=org,
            gym=gym,
            member_code="RAPI1-0001",
            full_name="Test Member",
            phone="+9779800000099",
            qr_secret=b"fixture-not-a-real-secret",
            risk_state=Member.RiskState.RED_LIST,
        )
        call = RetentionCall.objects.create(
            org=org, gym=gym, member=member, queue_date=date.today(), assigned_to=front_desk
        )
    return org, gym, front_desk, member, call


def test_complete_requires_an_outcome(setup):
    _org, gym, front_desk, _member, call = setup
    client = _client_for(front_desk, gym)

    response = client.post(f"/api/v1/retention/calls/{call.pk}/complete/", {}, format="json")

    assert response.status_code == 400
    with system_context():
        call.refresh_from_db()
    assert call.completed_at is None


def test_complete_with_a_valid_outcome_clears_the_queue_item(setup):
    _org, gym, front_desk, _member, call = setup
    client = _client_for(front_desk, gym)

    response = client.post(
        f"/api/v1/retention/calls/{call.pk}/complete/",
        {"outcome": "coming_back"},
        format="json",
    )

    assert response.status_code == 200, response.content
    with system_context():
        call.refresh_from_db()
    assert call.outcome == "coming_back"
    assert call.completed_at is not None

    # And it drops out of the default (incomplete-only) queue listing.
    listing = client.get("/api/v1/retention/calls/", {"queue_date": date.today().isoformat()})
    assert call.pk not in [row["id"] for row in listing.json()]


def test_call_back_outcome_requires_a_call_back_date(setup):
    _org, gym, front_desk, _member, call = setup
    client = _client_for(front_desk, gym)

    response = client.post(
        f"/api/v1/retention/calls/{call.pk}/complete/",
        {"outcome": "call_back"},
        format="json",
    )

    assert response.status_code == 400


def test_freeze_preview_requires_manager_role(setup):
    _org, gym, front_desk, _member, _call = setup
    client = _client_for(front_desk, gym)  # front_desk, not manager+

    response = client.post(
        "/api/v1/retention/freezes/preview",
        {"start_date": "2026-10-01", "end_date": "2026-10-10", "reason": "dashain"},
        format="json",
    )
    assert response.status_code == 403
