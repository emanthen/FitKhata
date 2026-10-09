"""Web Push via pywebpush + VAPID. A 404/410 from the push service means the
subscription itself is dead (the browser unregistered it, or it simply
expired) — not worth retrying, and not worth keeping around, so this deletes
the PushSubscription row itself before raising, which is why it needs the
model (not just the raw endpoint/keys) as its argument.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from django.conf import settings
from pywebpush import WebPushException, webpush

from notifications.providers.base import ProviderPermanentError, ProviderTransientError

if TYPE_CHECKING:
    from notifications.models import PushSubscription


def send(subscription: PushSubscription, title: str, body: str) -> None:
    try:
        webpush(
            subscription_info={
                "endpoint": subscription.endpoint,
                "keys": subscription.keys,
            },
            data=json.dumps({"title": title, "body": body}),
            vapid_private_key=settings.VAPID_PRIVATE_KEY,
            vapid_claims={"sub": f"mailto:{settings.VAPID_CONTACT_EMAIL}"},
        )
    except WebPushException as exc:
        status_code = exc.response.status_code if exc.response is not None else None
        if status_code in (404, 410):
            subscription.delete()
            raise ProviderPermanentError(f"Push subscription gone ({status_code})") from exc
        raise ProviderTransientError(str(exc)) from exc
