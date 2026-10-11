"""Business logic for public API keys (FR-12.3) and outgoing webhooks
(FR-12.4). Rule 9: views stay thin.
"""

from __future__ import annotations

import hashlib
import secrets
from typing import Any

from core.crypto import encrypt_bytes
from core.services import audit
from publicapi.models import ApiKey, WebhookSubscription

KEY_PREFIX_LENGTH = 10


def create_api_key(org: Any, name: str, scopes: list[str], actor: Any = None) -> tuple[ApiKey, str]:
    """Returns (api_key, raw_key) — the only time the raw key is ever
    available, same never-store-the-raw-value shape as
    attendance.services.register_gate_device.
    """
    raw_key = f"fk_live_{secrets.token_urlsafe(32)}"
    api_key = ApiKey.objects.create(
        org=org,
        name=name,
        key_prefix=raw_key[:KEY_PREFIX_LENGTH],
        key_hash=hashlib.sha256(raw_key.encode("utf-8")).hexdigest(),
        scopes=scopes,
        created_by=actor,
    )
    audit(api_key, "create", after={"name": name, "scopes": scopes}, actor=actor)
    return api_key, raw_key


def revoke_api_key(api_key: ApiKey, actor: Any = None) -> None:
    from django.utils import timezone

    api_key.revoked_at = timezone.now()
    api_key.save(update_fields=["revoked_at"])
    audit(api_key, "update", after={"revoked_at": api_key.revoked_at.isoformat()}, actor=actor)


def touch_api_key_last_used(api_key: ApiKey) -> None:
    from django.utils import timezone

    ApiKey.objects.filter(pk=api_key.pk).update(last_used_at=timezone.now())


def create_webhook_subscription(
    org: Any, url: str, events: list[str], secret: str, actor: Any = None
) -> WebhookSubscription:
    subscription = WebhookSubscription.objects.create(
        org=org,
        url=url,
        events=events,
        secret_encrypted=encrypt_bytes(secret.encode("utf-8")),
        created_by=actor,
    )
    audit(subscription, "create", after={"url": url, "events": events}, actor=actor)
    return subscription


def dispatch_webhook_event(org: Any, event: str, payload: dict[str, Any]) -> None:
    """Fires `event` to every active subscription this org has registered
    for it. Lazy-imports its own Celery task (same shape as
    notifications.services._enqueue's lazy import of notifications.tasks)
    to avoid a services<->tasks circular import.
    """
    from publicapi.models import WebhookDelivery
    from publicapi.tasks import deliver_webhook

    subscriptions = WebhookSubscription.objects.filter(org=org, is_active=True)
    for subscription in subscriptions:
        if event not in subscription.events:
            continue
        delivery = WebhookDelivery.objects.create(
            subscription=subscription, event=event, payload=payload
        )
        deliver_webhook.delay(str(delivery.pk))
