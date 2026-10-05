"""HTTP-level tests through DRF's APIClient — unlike the rest of this
package's tests (which call functions directly), these exercise routing,
serializers, and views together. Added after a real bug (register() tried
to re-verify an OTP code that verify_otp() had already deleted on success)
slipped past every direct-call unit test and only showed up testing the
actual endpoint from a browser.
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from accounts import otp
from accounts.models import User

pytestmark = pytest.mark.django_db

PHONE = "+9779855556666"


@pytest.fixture(autouse=True)
def _clean_redis():
    otp._redis.flushdb()
    yield
    otp._redis.flushdb()


@pytest.fixture
def client():
    return APIClient()


def test_register_flow_end_to_end(client):
    """send -> verify (new number) -> register, using the registration_token
    the verify step returns — not the spent OTP code."""
    send_resp = client.post("/api/v1/auth/otp/send", {"phone": PHONE}, format="json")
    assert send_resp.status_code == 204

    code = otp._redis.get(f"otp:code:{PHONE}")
    assert code is not None

    verify_resp = client.post(
        "/api/v1/auth/otp/verify", {"phone": PHONE, "code": code}, format="json"
    )
    assert verify_resp.status_code == 200
    body = verify_resp.json()
    assert body["user_exists"] is False
    assert body["registration_token"]

    register_resp = client.post(
        "/api/v1/auth/register",
        {
            "registration_token": body["registration_token"],
            "full_name": "Integration Test User",
            "password": "integrationtestpass123",
        },
        format="json",
    )
    assert register_resp.status_code == 201, register_resp.content
    register_body = register_resp.json()
    assert "access" in register_body
    assert "refresh" in register_body
    assert User.objects.filter(phone=PHONE).exists()


def test_register_rejects_a_reused_otp_code_directly(client):
    """The old (buggy) shape — resubmitting {phone, code} — is no longer
    what /register accepts at all; confirms the endpoint's contract changed
    rather than just happening to work."""
    response = client.post(
        "/api/v1/auth/register",
        {"phone": PHONE, "code": "000000", "full_name": "X", "password": "whatever123"},
        format="json",
    )
    assert response.status_code == 400


def test_register_token_cannot_be_reused(client):
    client.post("/api/v1/auth/otp/send", {"phone": PHONE}, format="json")
    code = otp._redis.get(f"otp:code:{PHONE}")
    verify_resp = client.post(
        "/api/v1/auth/otp/verify", {"phone": PHONE, "code": code}, format="json"
    )
    token = verify_resp.json()["registration_token"]

    first = client.post(
        "/api/v1/auth/register",
        {"registration_token": token, "full_name": "First", "password": "firstpass123"},
        format="json",
    )
    assert first.status_code == 201

    second = client.post(
        "/api/v1/auth/register",
        {"registration_token": token, "full_name": "Second", "password": "secondpass123"},
        format="json",
    )
    assert second.status_code == 400
