"""Common interface + credential resolution for billing/gateways/*.py."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from billing.models import GatewayCredential
from core.crypto import decrypt_bytes


class GatewayNotConfigured(Exception):
    pass


class GatewayVerificationFailed(Exception):
    """Signature mismatch, amount mismatch, or a non-success status from
    the provider — the caller must never proceed to collect_payment() when
    this is raised.
    """


@dataclass
class RedirectInstructions:
    """What the caller needs to send the member to the gateway. eSewa wants
    an auto-submitted HTML form (POST); Khalti and Fonepay hand back a
    ready-made URL to redirect to (GET) — `method` tells the caller which.
    """

    url: str
    method: str  # "GET" | "POST"
    fields: dict[str, str]  # POST form fields; empty for GET
    # The gateway's own reference for this attempt, when it hands one back
    # at initiate time (Khalti's pidx) — "" when it doesn't (eSewa has none
    # until the callback). The caller persists this onto Payment.gateway_ref
    # so a later re-verification (billing/tasks.py) has something to look
    # up even if the member never completes the redirect.
    reference: str = ""


@dataclass
class VerifiedResult:
    completed: bool
    gateway_ref: str
    raw_response: dict[str, Any]


class Gateway(Protocol):
    def initiate(self, payment: Any, *, return_url: str) -> RedirectInstructions:
        """`return_url` is one page the member PWA lands back on either way
        (success or failure/cancel) — neither eSewa nor Khalti gives the
        caller a reason to need two different URLs: the landing page
        itself checks the outcome (eSewa via the signed `data` query
        param it appends, Khalti via its own `pidx` + a lookup call)
        rather than being routed by which URL it came back to.
        """
        ...

    def verify(self, callback_data: dict[str, Any]) -> VerifiedResult: ...


def resolve_credential(gym: Any, provider: str) -> GatewayCredential:
    """Prefers a live credential, falls back to sandbox — a gym can keep
    both configured at once (sandbox for its own testing, live for real
    traffic), see billing/services.py's module docstring.
    """
    credential = GatewayCredential.objects.filter(
        gym=gym,
        provider=provider,
        environment=GatewayCredential.Environment.LIVE,
        is_active=True,
    ).first()
    if credential is None:
        credential = GatewayCredential.objects.filter(
            gym=gym,
            provider=provider,
            environment=GatewayCredential.Environment.SANDBOX,
            is_active=True,
        ).first()
    if credential is None:
        raise GatewayNotConfigured(f"No active {provider} credential configured for this gym.")
    return credential


def credential_secret(credential: GatewayCredential) -> str:
    return decrypt_bytes(bytes(credential.secret_encrypted)).decode("utf-8")
