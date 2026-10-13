"""FR-12.4: signs and delivers one webhook attempt, retrying with backoff
up to WebhookDelivery.MAX_ATTEMPTS -- same bind=True/self.retry shape as
notifications/tasks.py's per-channel send tasks.
"""

from __future__ import annotations

import hashlib
import hmac
import json

import requests
from celery import shared_task
from django.utils import timezone

from core.crypto import decrypt_bytes
from publicapi.models import WebhookDelivery
from publicapi.url_safety import UnsafeWebhookUrl, assert_safe_webhook_url

TIMEOUT_SECONDS = 5


def sign_payload(secret: str, body: bytes) -> str:
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def _backoff_seconds(attempt_count: int) -> int:
    return min(60 * (2 ** (attempt_count - 1)), 3600)


@shared_task(bind=True, max_retries=WebhookDelivery.MAX_ATTEMPTS)
def deliver_webhook(self, delivery_id: str) -> None:
    delivery = WebhookDelivery.objects.select_related("subscription").get(pk=delivery_id)
    subscription = delivery.subscription
    secret = decrypt_bytes(bytes(subscription.secret_encrypted)).decode("utf-8")
    body = json.dumps(delivery.payload, sort_keys=True, default=str).encode("utf-8")
    signature = sign_payload(secret, body)

    delivery.attempt_count += 1
    delivery.last_attempted_at = timezone.now()

    # Re-checked here, not just at subscription-create time: a hostname
    # that resolved to a public IP when the subscription was created can
    # be repointed at a private/metadata address by delivery time (DNS
    # rebinding) — this is the check that's actually load-bearing.
    # Rejected outright, not retried: no future attempt would pass either.
    try:
        assert_safe_webhook_url(subscription.url)
    except UnsafeWebhookUrl as exc:
        delivery.status = WebhookDelivery.Status.FAILED
        delivery.response_status = None
        delivery.response_body = str(exc)
        delivery.save(
            update_fields=["status", "attempt_count", "response_body", "last_attempted_at"]
        )
        return

    try:
        response = requests.post(
            subscription.url,
            data=body,
            headers={
                "content-type": "application/json",
                "X-FitKhata-Signature": signature,
                "X-FitKhata-Event": delivery.event,
            },
            timeout=TIMEOUT_SECONDS,
            allow_redirects=False,  # a redirect target was never validated above
        )
    except requests.RequestException as exc:
        _finish_attempt(delivery, response_status=None, response_body=str(exc))
        if delivery.attempt_count < WebhookDelivery.MAX_ATTEMPTS:
            raise self.retry(exc=exc, countdown=_backoff_seconds(delivery.attempt_count)) from exc
        return

    _finish_attempt(
        delivery, response_status=response.status_code, response_body=response.text[:2000]
    )
    delivered = 200 <= response.status_code < 300
    if not delivered and delivery.attempt_count < WebhookDelivery.MAX_ATTEMPTS:
        retry_exc = requests.HTTPError(f"webhook delivery got status {response.status_code}")
        raise self.retry(
            exc=retry_exc, countdown=_backoff_seconds(delivery.attempt_count)
        ) from retry_exc


def _finish_attempt(
    delivery: WebhookDelivery, *, response_status: int | None, response_body: str
) -> None:
    delivered = response_status is not None and 200 <= response_status < 300
    if delivered:
        delivery.status = WebhookDelivery.Status.DELIVERED
    elif delivery.attempt_count >= WebhookDelivery.MAX_ATTEMPTS:
        delivery.status = WebhookDelivery.Status.FAILED
    # else: stays PENDING, a retry is still coming.
    delivery.response_status = response_status
    delivery.response_body = response_body
    delivery.save(
        update_fields=[
            "status",
            "attempt_count",
            "response_status",
            "response_body",
            "last_attempted_at",
        ]
    )
