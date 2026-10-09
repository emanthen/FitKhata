"""Regression test for a real bug found while manually verifying the admin
UI: TotpSetupView's "reuse any existing unconfirmed device" check wasn't
atomic, so two concurrent calls (the exact React Strict Mode double-effect
case its own comment describes) could each see "no unconfirmed device" and
both create one — the user is shown whichever response lands first, but
TotpConfirmView's order_by("-id") then checks the *other*, never-displayed
device, and every code the user enters is rejected. Reproduced for real:
two unconfirmed TOTPDevice rows existed for one browser session that never
left the setup page.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest
from django.db import connection
from django_otp.plugins.otp_totp.models import TOTPDevice
from rest_framework.test import APIClient

from accounts.models import User
from accounts.tokens import issue_tokens_for_user


def _totp_now(secret_b32: str) -> str:
    key = base64.b32decode(secret_b32.upper())
    counter = int(time.time() // 30)
    digest = hmac.new(key, counter.to_bytes(8, "big"), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = (int.from_bytes(digest[offset : offset + 4], "big") & 0x7FFFFFFF) % 1_000_000
    return str(code).zfill(6)


def _client_for(user: User) -> APIClient:
    tokens = issue_tokens_for_user(user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
    return client


@pytest.mark.django_db
def test_setup_then_confirm_with_the_displayed_secret_succeeds():
    user = User.objects.create_user(phone="+9779822220001", password="x")
    client = _client_for(user)

    setup_response = client.post("/api/v1/auth/totp/setup")
    assert setup_response.status_code == 200, setup_response.content
    secret = setup_response.json()["secret"]

    confirm_response = client.post(
        "/api/v1/auth/totp/confirm", {"code": _totp_now(secret)}, format="json"
    )

    assert confirm_response.status_code == 204, confirm_response.content


@pytest.mark.django_db(transaction=True)
def test_concurrent_setup_calls_resolve_to_one_device_not_two():
    """Real concurrent requests (own DB connections per thread), not just
    sequential calls — a sequential double-call wouldn't have caught the
    original bug, since the first call's commit was already visible to the
    second even without locking. Only genuine concurrency exercises the
    check-then-create race.
    """
    user = User.objects.create_user(phone="+9779822220002", password="x")
    tokens = issue_tokens_for_user(user)

    def call_setup() -> dict:
        try:
            client = APIClient()
            client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
            response = client.post("/api/v1/auth/totp/setup")
            return response.json()
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(call_setup) for _ in range(2)]
        results = [future.result() for future in as_completed(futures)]

    assert results[0]["secret"] == results[1]["secret"]
    assert TOTPDevice.objects.filter(user=user, confirmed=False).count() == 1

    # And the secret shown to (either of) the concurrent callers actually
    # verifies — the real end-to-end proof, not just a row count.
    client = _client_for(user)
    confirm_response = client.post(
        "/api/v1/auth/totp/confirm", {"code": _totp_now(results[0]["secret"])}, format="json"
    )
    assert confirm_response.status_code == 204, confirm_response.content
