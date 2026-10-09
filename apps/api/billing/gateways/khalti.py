"""Khalti KPG-2 ePayment — https://docs.khalti.com/khalti-epayment/

Field names/endpoints below are from Khalti's own published docs (fetched
2026-10-05). Unlike eSewa, Khalti has no single shared public sandbox
secret — a free test secret key is obtained per-integrator by registering
at test-admin.khalti.com, so nothing here hardcodes one; a gym's sandbox
GatewayCredential has to carry its own.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import requests

from billing.gateways.base import (
    GatewayVerificationFailed,
    RedirectInstructions,
    VerifiedResult,
    credential_secret,
    resolve_credential,
)
from billing.models import GatewayCredential, Payment

BASE_URL: dict[str, str] = {
    GatewayCredential.Environment.SANDBOX: "https://dev.khalti.com/api/v2/",
    GatewayCredential.Environment.LIVE: "https://khalti.com/api/v2/",
}


def _amount_paisa(amount_npr: Decimal) -> int:
    # Khalti's amount is NPR*100 as an integer — paisa, not rupees.
    return int((amount_npr * 100).to_integral_value())


class KhaltiGateway:
    def initiate(self, payment: Payment, *, return_url: str) -> RedirectInstructions:
        credential = resolve_credential(payment.gym, GatewayCredential.Provider.KHALTI)
        secret = credential_secret(credential)

        response = requests.post(
            f"{BASE_URL[credential.environment]}epayment/initiate/",
            headers={"Authorization": f"Key {secret}"},
            json={
                "return_url": return_url,
                "website_url": return_url,
                "amount": _amount_paisa(payment.amount_npr),
                "purchase_order_id": str(payment.transaction_uuid),
                "purchase_order_name": f"FitKhata membership ({payment.member.member_code})",
            },
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()
        return RedirectInstructions(
            url=data["payment_url"], method="GET", fields={}, reference=data["pidx"]
        )

    def verify(self, callback_data: dict[str, Any]) -> VerifiedResult:
        """callback_data = {"pidx": str, "gym": Gym, "expected_amount_paisa":
        int}. Only `status == "Completed"` **and** a matching amount
        proceed — a status-only check would accept a lookup for a
        tampered/lower pidx amount.
        """
        gym = callback_data["gym"]
        pidx = callback_data["pidx"]
        credential = resolve_credential(gym, GatewayCredential.Provider.KHALTI)
        secret = credential_secret(credential)

        response = requests.post(
            f"{BASE_URL[credential.environment]}epayment/lookup/",
            headers={"Authorization": f"Key {secret}"},
            json={"pidx": pidx},
            timeout=15,
        )
        response.raise_for_status()
        result = response.json()

        expected_amount = callback_data.get("expected_amount_paisa")
        is_completed_status = result.get("status") == "Completed"
        amount_matches = expected_amount is None or result.get("total_amount") == expected_amount

        if is_completed_status and not amount_matches:
            raise GatewayVerificationFailed(
                f"Khalti amount mismatch: expected {expected_amount} paisa, "
                f"got {result.get('total_amount')}."
            )

        return VerifiedResult(
            completed=is_completed_status and amount_matches,
            gateway_ref=result.get("transaction_id", ""),
            raw_response=result,
        )
