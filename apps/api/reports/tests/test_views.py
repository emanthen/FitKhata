"""HTTP-level smoke test for the export query param — regression for a real
bug: naming it "format" collided with DRF's reserved URL_FORMAT_OVERRIDE
query param (default renderers are json/api only, so ?format=csv got
intercepted by content negotiation and 404'd via Http404 before the view
ever ran). Caught via manual browser verification, not by test_exporters.py
(which calls the exporter functions directly, bypassing routing entirely).
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from accounts.models import StaffRole, User
from accounts.tokens import issue_tokens_for_user
from core.context import system_context
from gyms.models import Gym, Organization

pytestmark = pytest.mark.django_db


def _client_for(user: User, gym: Gym) -> APIClient:
    tokens = issue_tokens_for_user(user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}", HTTP_X_GYM_ID=str(gym.pk))
    return client


@pytest.fixture
def manager_setup():
    with system_context():
        org = Organization.objects.create(name="Reports View Test Org")
        gym = Gym.objects.create(org=org, code="RVT1", name="Reports View Test Gym")
        user = User.objects.create_user(phone="+9779822000099", password="x", full_name="Manager")
        StaffRole.objects.create(org=org, gym=gym, user=user, role=StaffRole.Role.MANAGER)
    return user, gym


def test_dues_ageing_export_query_param_does_not_404(manager_setup):
    user, gym = manager_setup
    client = _client_for(user, gym)

    response = client.get("/api/v1/reports/dues-ageing", {"export": "csv"})

    assert response.status_code == 200
    assert response["Content-Type"] == "text/csv"
