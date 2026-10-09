"""eSewa ePay v2 — https://developer.esewa.com.np/pages/Epay

Field names, signing format, and endpoints below are taken directly from
eSewa's own published docs (fetched 2026-10-05), not guessed:
- Signed message: "total_amount=<>,transaction_uuid=<>,product_code=<>"
  (comma-joined key=value, exact field order, HMAC-SHA256, base64 output).
- Sandbox product_code "EPAYTEST" + secret "8gBm/:&EnhH.1/q" are eSewa's
  own published, shared test credentials — not a secret to protect, every
  integrator uses the same ones.
- Status values: PENDING, COMPLETE, FULL_REFUND, PARTIAL_REFUND,
  AMBIGUOUS, NOT_FOUND, CANCELED — only COMPLETE proceeds.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
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

SIGNED_FIELD_NAMES = "total_amount,transaction_uuid,product_code"

FORM_URL: dict[str, str] = {
    GatewayCredential.Environment.SANDBOX: "https://rc-epay.esewa.com.np/api/epay/main/v2/form",
    GatewayCredential.Environment.LIVE: "https://epay.esewa.com.np/api/epay/main/v2/form",
}
STATUS_URL: dict[str, str] = {
    GatewayCredential.Environment.SANDBOX: "https://rc.esewa.com.np/api/epay/transaction/status/",
    GatewayCredential.Environment.LIVE: "https://esewa.com.np/api/epay/transaction/status/",
}


def _sign(secret: str, total_amount: str, transaction_uuid: str, product_code: str) -> str:
    message = (
        f"total_amount={total_amount},"
        f"transaction_uuid={transaction_uuid},"
        f"product_code={product_code}"
    )
    digest = hmac.new(secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).digest()
    return base64.b64encode(digest).decode("ascii")


class EsewaGateway:
    def initiate(self, payment: Payment, *, return_url: str) -> RedirectInstructions:
        credential = resolve_credential(payment.gym, GatewayCredential.Provider.ESEWA)
        secret = credential_secret(credential)
        total_amount = f"{payment.amount_npr:.2f}"
        transaction_uuid = str(payment.transaction_uuid)
        product_code = credential.merchant_code

        signature = _sign(secret, total_amount, transaction_uuid, product_code)

        fields = {
            "amount": total_amount,
            "tax_amount": "0",
            "product_service_charge": "0",
            "product_delivery_charge": "0",
            "total_amount": total_amount,
            "transaction_uuid": transaction_uuid,
            "product_code": product_code,
            "success_url": return_url,
            "failure_url": return_url,
            "signed_field_names": SIGNED_FIELD_NAMES,
            "signature": signature,
        }
        return RedirectInstructions(
            url=FORM_URL[credential.environment], method="POST", fields=fields
        )

    def verify(self, callback_data: dict[str, Any]) -> VerifiedResult:
        """callback_data = {"data": "<base64 string from the success_url's
        ?data= query param>", "gym": <Gym>}. Re-verifies the signature
        eSewa sent (defense against a tampered redirect) before even
        considering the status-check API call.
        """
        gym = callback_data["gym"]
        decoded = json.loads(base64.b64decode(callback_data["data"]))

        credential = resolve_credential(gym, GatewayCredential.Provider.ESEWA)
        secret = credential_secret(credential)
        expected_signature = _sign(
            secret, decoded["total_amount"], decoded["transaction_uuid"], decoded["product_code"]
        )
        if not hmac.compare_digest(expected_signature, decoded.get("signature", "")):
            raise GatewayVerificationFailed("eSewa callback signature does not match.")
        if decoded.get("status") != "COMPLETE":
            return VerifiedResult(completed=False, gateway_ref="", raw_response=decoded)

        # Signature alone isn't enough to trust a success — eSewa's own
        # integration guidance is to re-confirm against the status-check
        # API rather than act on the redirect payload alone.
        result = self.check_status(
            gym, decoded["total_amount"], decoded["transaction_uuid"], decoded["product_code"]
        )
        return VerifiedResult(
            completed=result.completed,
            gateway_ref=result.gateway_ref,
            raw_response={"callback": decoded, "status_check": result.raw_response},
        )

    def check_status(
        self, gym: Any, total_amount: str, transaction_uuid: str, product_code: str | None = None
    ) -> VerifiedResult:
        """The status-check API alone, with no signed callback payload
        needed — what billing/tasks.py's pending-payment re-verification
        job calls (it only ever has what it already stored, never a
        redirect `data` param to decode and verify a signature over).
        """
        credential = resolve_credential(gym, GatewayCredential.Provider.ESEWA)
        response = requests.get(
            STATUS_URL[credential.environment],
            params={
                "product_code": product_code or credential.merchant_code,
                "total_amount": total_amount,
                "transaction_uuid": transaction_uuid,
            },
            timeout=15,
        )
        response.raise_for_status()
        status_result = response.json()
        return VerifiedResult(
            completed=status_result.get("status") == "COMPLETE",
            gateway_ref=status_result.get("ref_id", "") or "",
            raw_response=status_result,
        )
