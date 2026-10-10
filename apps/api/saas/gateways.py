"""FitKhata's own eSewa/Khalti collection — reuses billing/gateways/*.py
completely unchanged. Gateway.initiate()/verify() only ever read
payment.gym/.amount_npr/.transaction_uuid/.member off whatever object
they're given (confirmed by billing/views.py's own _StubPayment/
_StubMember, used there to test-fire a gateway without a real Payment
row) — so a lightweight duck-typed stub works exactly as well as a real
billing.Payment, without coupling SaaS billing to the tenant-scoped
Payment/collect_payment machinery (member/referral/membership side
effects that don't apply to a platform-level charge).

Credentials are resolved the normal way (billing.gateways.resolve_credential)
against the fixed "FitKhata Platform" Gym seeded in
migrations/0003_seed_fitkhata_platform_gym.py — set those GatewayCredential
rows per environment (not committed), same as any tenant gym's.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import UUID

from billing.gateways import Gateway, get_gateway
from billing.gateways.base import RedirectInstructions, VerifiedResult
from gyms.models import Gym
from saas.constants import FITKHATA_PLATFORM_GYM_ID


@dataclass
class _PlatformPayee:
    member_code: str


@dataclass
class _PlatformPayment:
    gym: Gym
    amount_npr: Decimal
    transaction_uuid: UUID
    member: _PlatformPayee


def _fitkhata_gym() -> Gym:
    return Gym.objects.get(pk=FITKHATA_PLATFORM_GYM_ID)


def initiate_platform_payment(
    amount_npr: Decimal, transaction_uuid: UUID, provider: str, *, reference: str, return_url: str
) -> RedirectInstructions:
    """`reference` is a human-readable label (e.g. a SaasInvoice number) —
    passed through as the stub payment's member_code, the only thing
    billing.gateways.* use from `.member`.
    """
    stub = _PlatformPayment(
        gym=_fitkhata_gym(),
        amount_npr=amount_npr,
        transaction_uuid=transaction_uuid,
        member=_PlatformPayee(member_code=reference),
    )
    gateway: Gateway = get_gateway(provider)
    return gateway.initiate(stub, return_url=return_url)


def verify_platform_payment(provider: str, callback_data: dict[str, Any]) -> VerifiedResult:
    """callback_data gets `gym` injected automatically — eSewa's verify()
    needs it to re-resolve the credential, same as MemberRenewalCallbackView
    does by hand for tenant payments.
    """
    gateway: Gateway = get_gateway(provider)
    return gateway.verify({**callback_data, "gym": _fitkhata_gym()})
