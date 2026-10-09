from __future__ import annotations

import hashlib
import hmac

import pytest

from notifications.providers.whatsapp import verify_webhook_signature

APP_SECRET = "test-app-secret"


def _sign(body: bytes, secret: str = APP_SECRET) -> str:
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


@pytest.fixture(autouse=True)
def _app_secret(settings):
    settings.WHATSAPP_APP_SECRET = APP_SECRET


def test_valid_signature_is_accepted():
    body = b'{"entry": []}'
    assert verify_webhook_signature(body, _sign(body)) is True


def test_tampered_body_is_rejected():
    body = b'{"entry": []}'
    signature = _sign(body)
    tampered_body = b'{"entry": ["injected"]}'
    assert verify_webhook_signature(tampered_body, signature) is False


def test_signature_signed_with_wrong_secret_is_rejected():
    body = b'{"entry": []}'
    wrong_signature = _sign(body, secret="not-the-real-secret")
    assert verify_webhook_signature(body, wrong_signature) is False


def test_missing_header_is_rejected():
    assert verify_webhook_signature(b'{"entry": []}', None) is False


def test_malformed_header_without_sha256_prefix_is_rejected():
    assert verify_webhook_signature(b'{"entry": []}', "not-a-real-signature") is False
