"""Meta WhatsApp Cloud API — https://developers.facebook.com/docs/whatsapp/cloud-api

Template messages only (Meta requires a pre-approved template for any
business-initiated message) + the delivery-status webhook, verified via
X-Hub-Signature-256 the same way every Meta webhook integration must.
"""

from __future__ import annotations

import hashlib
import hmac
from typing import Any

import requests
from django.conf import settings

from notifications.providers.base import ProviderPermanentError, ProviderTransientError

GRAPH_API_VERSION = "v20.0"

# Statuses Meta's Graph API returns that mean "this will never succeed by
# retrying the same request" — everything else (network errors, 5xx, rate
# limiting) is treated as transient.
_PERMANENT_ERROR_CODES = {
    131026,  # message undeliverable
    131021,  # recipient is not a WhatsApp user / invalid number
    132001,  # template does not exist / not approved
}


def send(phone: str, template_name: str, language: str, variables: list[str]) -> str:
    """Returns the provider's message id (Notification.provider_ref)."""
    url = (
        f"https://graph.facebook.com/{GRAPH_API_VERSION}/"
        f"{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"
    )
    components = (
        [{"type": "body", "parameters": [{"type": "text", "text": v} for v in variables]}]
        if variables
        else []
    )
    body: dict[str, Any] = {
        "messaging_product": "whatsapp",
        "to": phone.removeprefix("+"),
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": language},
            "components": components,
        },
    }
    try:
        response = requests.post(
            url,
            headers={"Authorization": f"Bearer {settings.WHATSAPP_CLOUD_API_TOKEN}"},
            json=body,
            timeout=15,
        )
    except requests.RequestException as exc:
        raise ProviderTransientError(str(exc)) from exc

    if response.status_code >= 500:
        raise ProviderTransientError(f"WhatsApp Cloud API {response.status_code}: {response.text}")
    if response.status_code >= 400:
        error = response.json().get("error", {})
        if error.get("code") in _PERMANENT_ERROR_CODES:
            raise ProviderPermanentError(error.get("message", response.text))
        raise ProviderTransientError(f"WhatsApp Cloud API {response.status_code}: {response.text}")

    return response.json()["messages"][0]["id"]


def verify_webhook_signature(request_body: bytes, signature_header: str | None) -> bool:
    """signature_header is the raw X-Hub-Signature-256 header value, e.g.
    "sha256=<hex>". Constant-time compare — rule: never == a secret-derived value.
    """
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(
        settings.WHATSAPP_APP_SECRET.encode("utf-8"), request_body, hashlib.sha256
    ).hexdigest()
    provided = signature_header.removeprefix("sha256=")
    return hmac.compare_digest(expected, provided)
