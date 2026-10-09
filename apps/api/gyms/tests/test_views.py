"""gyms/ had no test coverage before Phase 7 — this file only covers the
one piece of real new behavior Phase 7 added to it: GymCreateView seeding
coaching's default diet plans (coaching/services.py::seed_default_diet_plans),
not a general backfill of this app's whole test suite.
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from accounts.models import StaffRole, User
from accounts.tokens import issue_tokens_for_user
from coaching.models import DietPlan
from core.context import system_context
from gyms.models import Organization

pytestmark = pytest.mark.django_db


def test_creating_a_gym_seeds_the_default_diet_plans():
    with system_context():
        org = Organization.objects.create(name="Diet Seed Test Org")
        owner = User.objects.create_user(phone="+9774000002001", password="x")
        StaffRole.objects.create(user=owner, org=org, gym=None, role=StaffRole.Role.OWNER)

    tokens = issue_tokens_for_user(owner)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

    response = client.post(
        "/api/v1/gyms",
        {"org": str(org.pk), "code": "DST1", "name": "Diet Seed Test Gym"},
        format="json",
    )

    assert response.status_code == 201, response.content
    gym_id = response.json()["id"]
    with system_context():
        plan_names = set(DietPlan.objects.filter(gym_id=gym_id).values_list("name", flat=True))
    assert "Dal-Bhat Standard" in plan_names
    assert "Sel Roti Festival Treat" in plan_names
    assert len(plan_names) == 7
