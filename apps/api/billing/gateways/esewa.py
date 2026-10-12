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

SIGNED_FIELD_NAMES = "total_amount,transaction_uuid,product_code"

# The response's signed_field_names must at minimum cover these — the
# fields verify()'s cross-check (against the actual Payment row) and
# status gate depend on actually having been part of the signature.
REQUIRED_RESPONSE_FIELDS = {"total_amount", "transaction_uuid", "product_code", "status"}

FORM_URL: dict[str, str] = {
    GatewayCredential.Environment.SANDBOX: "https://rc-epay.esewa.com.np/api/epay/main/v2/form",
    GatewayCredential.Environment.LIVE: "https://epay.esewa.com.np/api/epay/main/v2/form",
}
STATUS_URL: dict[str, str] = {
    GatewayCredential.Environment.SANDBOX: "https://rc.esewa.com.np/api/epay/transaction/status/",
    GatewayCredential.Environment.LIVE: "https://esewa.com.np/api/epay/transaction/status/",
}


def _hmac_b64(secret: str, message: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).digest()
    return base64.b64encode(digest).decode("ascii")


def _sign(secret: str, total_amount: str, transaction_uuid: str, product_code: str) -> str:
    message = (
        f"total_amount={total_amount},"
        f"transaction_uuid={transaction_uuid},"
        f"product_code={product_code}"
    )
    return _hmac_b64(secret, message)


def _response_message(decoded: dict[str, Any], signed_field_names: str) -> str:
    """eSewa's response names its OWN signed field set in signed_field_names
    (self-describing, not assumed to match the request's 3-field formula —
    see this module's docstring history for why hardcoding one fixed list
    for both directions was wrong). Builds the message in exactly the order
    that field list gives, each as "field=value" from the decoded payload.
    """
    fields = [f.strip() for f in signed_field_names.split(",") if f.strip()]
    return ",".join(f"{field}={decoded.get(field, '')}" for field in fields)


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
        ?data= query param>", "gym": <Gym>, "payment": <Payment>}.
        Re-verifies the signature eSewa sent (defense against a tampered
        redirect), then — critically — that the signed payload is actually
        FOR this specific payment, before even considering the
        status-check API call. Without that second check, a genuinely
        signed callback for one (e.g. small, already-paid) transaction
        could be replayed against a different payment_id and complete it
        instead; the signature alone only proves the blob wasn't tampered
        with, not which payment it's allowed to confirm.
        """
        gym = callback_data["gym"]
        payment = callback_data["payment"]
        decoded = json.loads(base64.b64decode(callback_data["data"]))

        credential = resolve_credential(gym, GatewayCredential.Provider.ESEWA)
        secret = credential_secret(credential)

        signed_field_names = decoded.get("signed_field_names", "")
        present_fields = {f.strip() for f in signed_field_names.split(",")}
        if not REQUIRED_RESPONSE_FIELDS.issubset(present_fields):
            raise GatewayVerificationFailed(
                "eSewa callback's signed_field_names is missing required fields."
            )

        expected_signature = _hmac_b64(secret, _response_message(decoded, signed_field_names))
        if not hmac.compare_digest(expected_signature, decoded.get("signature", "")):
            raise GatewayVerificationFailed("eSewa callback signature does not match.")

        # The blob is genuinely eSewa-signed, but only proves it's valid
        # for ITS OWN embedded transaction_uuid/total_amount — cross-check
        # those against the specific payment this call was asked to
        # confirm before trusting anything further.
        if decoded.get("transaction_uuid") != str(payment.transaction_uuid):
            raise GatewayVerificationFailed(
                "eSewa callback transaction_uuid does not match this payment."
            )
        if Decimal(str(decoded.get("total_amount", "0"))) != payment.amount_npr:
            raise GatewayVerificationFailed("eSewa callback amount does not match this payment.")
        if decoded.get("product_code") != credential.merchant_code:
            raise GatewayVerificationFailed(
                "eSewa callback product_code does not match this gym's credential."
            )

        if decoded.get("status") != "COMPLETE":
            return VerifiedResult(completed=False, gateway_ref="", raw_response=decoded)

        # Signature + payment match alone isn't enough to trust a success —
        # eSewa's own integration guidance is to re-confirm against the
        # status-check API. Use the PAYMENT's own values here, never the
        # decoded ones: the cross-check above makes them equal today, but
        # anchoring to the payment is what actually makes this safe, not
        # the fact that they happen to match right now.
        result = self.check_status(
            gym,
            f"{payment.amount_npr:.2f}",
            str(payment.transaction_uuid),
            credential.merchant_code,
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
