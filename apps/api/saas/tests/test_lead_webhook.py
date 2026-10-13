"""FR-12.6: Facebook Lead Ads webhook (verify-token handshake, signature
check, lead capture) and the platform-staff lead list -- HTTP level, same
APIClient convention as test_views.py's other platform-permission tests.
"""

from __future__ import annotations

import hashlib
import hmac
import json

import pytest
from django.test import override_settings
from django_otp.plugins.otp_totp.models import TOTPDevice
from rest_framework.test import APIClient

from accounts.models import User
from accounts.tokens import issue_tokens_for_user
from core.context import system_context
from saas.models import Lead

pytestmark = pytest.mark.django_db

APP_SECRET = "test-fb-app-secret"
VERIFY_TOKEN = "test-verify-token"


def _signed_post(client: APIClient, path: str, payload: dict) -> object:
    body = json.dumps(payload).encode("utf-8")
    signature = hmac.new(APP_SECRET.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return client.post(
        path,
        data=body,
        content_type="application/json",
        HTTP_X_HUB_SIGNATURE_256=f"sha256={signature}",
    )


@override_settings(FACEBOOK_APP_SECRET=APP_SECRET, FACEBOOK_LEAD_WEBHOOK_VERIFY_TOKEN=VERIFY_TOKEN)
def test_webhook_handshake_echoes_the_challenge_for_the_right_verify_token():
    client = APIClient()

    response = client.get(
        "/api/v1/webhooks/facebook-leads",
        {"hub.mode": "subscribe", "hub.verify_token": VERIFY_TOKEN, "hub.challenge": "12345"},
    )

    assert response.status_code == 200
    assert response.content == b"12345"


@override_settings(FACEBOOK_APP_SECRET=APP_SECRET, FACEBOOK_LEAD_WEBHOOK_VERIFY_TOKEN=VERIFY_TOKEN)
def test_webhook_handshake_rejects_the_wrong_verify_token():
    client = APIClient()

    response = client.get(
        "/api/v1/webhooks/facebook-leads",
        {"hub.mode": "subscribe", "hub.verify_token": "wrong", "hub.challenge": "12345"},
    )

    assert response.status_code == 403


@override_settings(FACEBOOK_APP_SECRET=APP_SECRET, FACEBOOK_LEAD_WEBHOOK_VERIFY_TOKEN=VERIFY_TOKEN)
def test_webhook_post_rejects_an_unsigned_request():
    client = APIClient()

    response = client.post(
        "/api/v1/webhooks/facebook-leads",
        data=json.dumps({"entry": []}),
        content_type="application/json",
    )

    assert response.status_code == 403
    with system_context():
        assert Lead.objects.count() == 0


@override_settings(FACEBOOK_APP_SECRET=APP_SECRET, FACEBOOK_LEAD_WEBHOOK_VERIFY_TOKEN=VERIFY_TOKEN)
def test_webhook_post_rejects_a_bad_signature():
    client = APIClient()
    body = json.dumps({"entry": []}).encode("utf-8")
    bad_signature = hmac.new(b"not-the-real-secret", body, hashlib.sha256).hexdigest()

    response = client.post(
        "/api/v1/webhooks/facebook-leads",
        data=body,
        content_type="application/json",
        HTTP_X_HUB_SIGNATURE_256=f"sha256={bad_signature}",
    )

    assert response.status_code == 403


@override_settings(FACEBOOK_APP_SECRET=APP_SECRET, FACEBOOK_LEAD_WEBHOOK_VERIFY_TOKEN=VERIFY_TOKEN)
def test_webhook_post_creates_one_lead_per_leadgen_change():
    client = APIClient()
    payload = {
        "object": "page",
        "entry": [
            {
                "id": "123",
                "changes": [
                    {
                        "field": "leadgen",
                        "value": {"leadgen_id": "999", "form_id": "1", "page_id": "123"},
                    }
                ],
            }
        ],
    }

    response = _signed_post(client, "/api/v1/webhooks/facebook-leads", payload)

    assert response.status_code == 200
    assert response.json() == {"created": 1}
    with system_context():
        lead = Lead.objects.get()
        assert lead.source == "facebook_lead_ads"
        assert lead.raw_payload["leadgen_id"] == "999"
        assert lead.status == Lead.Status.NEW


@override_settings(FACEBOOK_APP_SECRET=APP_SECRET, FACEBOOK_LEAD_WEBHOOK_VERIFY_TOKEN=VERIFY_TOKEN)
def test_webhook_post_ignores_non_leadgen_changes():
    client = APIClient()
    payload = {"entry": [{"changes": [{"field": "something_else", "value": {}}]}]}

    response = _signed_post(client, "/api/v1/webhooks/facebook-leads", payload)

    assert response.status_code == 200
    assert response.json() == {"created": 0}


@override_settings(FACEBOOK_APP_SECRET=APP_SECRET, FACEBOOK_LEAD_WEBHOOK_VERIFY_TOKEN=VERIFY_TOKEN)
def test_webhook_rate_limits_after_the_configured_threshold():
    from django.core.cache import cache

    client = APIClient()
    cache.clear()
    try:
        statuses = []
        for _ in range(70):  # rate is 60/m -- stop well past it or on first 429
            response = client.get(
                "/api/v1/webhooks/facebook-leads",
                {"hub.mode": "subscribe", "hub.verify_token": "wrong", "hub.challenge": "x"},
            )
            statuses.append(response.status_code)
            if response.status_code == 429:
                break
        assert 429 in statuses
    finally:
        cache.clear()


def _client_for(user: User) -> APIClient:
    tokens = issue_tokens_for_user(user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
    return client


def test_lead_list_requires_platform_staff():
    with system_context():
        non_staff = User.objects.create_user(phone="+9779811000020", password="x")
    client = _client_for(non_staff)

    response = client.get("/api/v1/platform/leads")

    assert response.status_code == 403


def test_lead_list_returns_captured_leads_for_platform_staff():
    with system_context():
        staff_user = User.objects.create_user(
            phone="+9779811000021", password="x", is_staff=True
        )
        TOTPDevice.objects.create(user=staff_user, name="default", confirmed=True)
        Lead.objects.create(full_name="Jane Doe", phone="+9779800000000")
    client = _client_for(staff_user)

    response = client.get("/api/v1/platform/leads")

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["full_name"] == "Jane Doe"
