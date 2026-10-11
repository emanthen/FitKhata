from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from core.context import system_context
from gyms.models import Gym, Organization
from publicapi.authentication import authenticate_api_key
from publicapi.permissions import require_scope
from publicapi.services import create_api_key, revoke_api_key

pytestmark = pytest.mark.django_db


@pytest.fixture
def org():
    with system_context():
        return Organization.objects.create(name="API Key Test Org")


@pytest.fixture
def gym(org):
    with system_context():
        return Gym.objects.create(org=org, code="APK1", name="API Key Test Gym")


# --- create_api_key / authenticate_api_key -------------------------------


def test_create_api_key_never_stores_the_raw_key(org):
    with system_context():
        api_key, raw_key = create_api_key(org, "Zapier integration", ["members:read"])

    assert raw_key.startswith("fk_live_")
    assert api_key.key_hash != raw_key
    assert api_key.key_prefix == raw_key[:10]


def test_authenticate_api_key_resolves_a_valid_key(org):
    with system_context():
        _, raw_key = create_api_key(org, "Zapier integration", ["members:read"])

    resolved = authenticate_api_key(f"ApiKey {raw_key}")
    assert resolved is not None
    assert resolved.org_id == org.pk


def test_authenticate_api_key_rejects_a_wrong_key(org):
    with system_context():
        create_api_key(org, "Zapier integration", ["members:read"])

    assert authenticate_api_key("ApiKey not-a-real-key") is None


def test_authenticate_api_key_rejects_a_revoked_key(org):
    with system_context():
        api_key, raw_key = create_api_key(org, "Zapier integration", ["members:read"])
        revoke_api_key(api_key)

    assert authenticate_api_key(f"ApiKey {raw_key}") is None


def test_authenticate_api_key_ignores_non_apikey_headers(org):
    with system_context():
        _, raw_key = create_api_key(org, "Zapier integration", ["members:read"])

    assert authenticate_api_key(f"Bearer {raw_key}") is None
    assert authenticate_api_key("") is None


# --- require_scope ---------------------------------------------------------


class _FakeRequest:
    def __init__(self, api_key):
        self.api_key = api_key


def test_require_scope_allows_a_key_with_the_scope(org):
    with system_context():
        api_key, _ = create_api_key(org, "k", ["members:read", "invoices:read"])

    permission = require_scope("members:read")()
    assert permission.has_permission(_FakeRequest(api_key), None) is True


def test_require_scope_denies_a_key_without_the_scope(org):
    with system_context():
        api_key, _ = create_api_key(org, "k", ["invoices:read"])

    permission = require_scope("members:read")()
    assert permission.has_permission(_FakeRequest(api_key), None) is False


def test_require_scope_denies_when_there_is_no_api_key():
    permission = require_scope("members:read")()
    assert permission.has_permission(_FakeRequest(None), None) is False


# --- rate limiting (FR-12.3) ----------------------------------------------


def test_public_api_rate_limits_after_the_configured_threshold(org, gym):
    with system_context():
        _, raw_key = create_api_key(org, "Rate limit test key", ["members:read"])

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"ApiKey {raw_key}")

    statuses = []
    for _ in range(110):  # rate is 100/m -- stop well past it or on first 429
        response = client.get("/api/public/v1/members")
        statuses.append(response.status_code)
        if response.status_code == 429:
            break

    assert 429 in statuses
