"""Fonepay dynamic QR — desk-only (FR-4.x): the front desk generates a QR
for the exact amount owed, the member scans and pays from their banking
app, the desk polls for completion. Field names/endpoints below are from
Fonepay's public merchant API reference (fetched 2026-10-05) — no
universally shared sandbox credential exists for Fonepay (unlike eSewa's
EPAYTEST), a gym's own merchant/username/password/HMAC key are required
even for sandbox testing.

Unlike eSewa (one shared secret) and Khalti (one secret key), Fonepay
needs four credential pieces: merchant_code, username, password, and a
separate HMAC-SHA512 signing key. merchant_code -> GatewayCredential.
merchant_code; username -> GatewayCredential.extra["username"] (not
secret); password + HMAC key -> both inside secret_encrypted as JSON
(both are sensitive, so both get encrypted, unlike username).
"""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any

import requests

from billing.gateways.base import (
    GatewayVerificationFailed,
    RedirectInstructions,
    VerifiedResult,
    resolve_credential,
)
from billing.models import GatewayCredential, Payment
from core.crypto import decrypt_bytes

BASE_URL: dict[str, str] = {
    GatewayCredential.Environment.SANDBOX: "https://uat-new-merchant-api.fonepay.com/api",
    GatewayCredential.Environment.LIVE: "https://merchantapi.fonepay.com/api",
}
QR_DOWNLOAD_PATH = "/merchant/merchantDetailsForThirdParty/thirdPartyDynamicQrDownload"
QR_STATUS_PATH = "/merchant/merchantDetailsForThirdParty/thirdPartyDynamicQrGetStatus"


def _secrets(credential: GatewayCredential) -> tuple[str, str]:
    """Returns (password, hmac_key) — both packed as JSON inside
    secret_encrypted, see this module's docstring.
    """
    payload = json.loads(decrypt_bytes(bytes(credential.secret_encrypted)))
    return payload["password"], payload["hmac_key"]


def _sign(hmac_key: str, *parts: str) -> str:
    message = ",".join(parts)
    return hmac.new(hmac_key.encode("utf-8"), message.encode("utf-8"), hashlib.sha512).hexdigest()


class FonepayGateway:
    def initiate(self, payment: Payment, *, return_url: str = "") -> RedirectInstructions:
        """return_url is unused — Fonepay has no redirect step, the desk
        stays on the same page and polls verify()/the websocket for this
        prn. Kept in the signature only so FonepayGateway still satisfies
        the common Gateway protocol.
        """
        credential = resolve_credential(payment.gym, GatewayCredential.Provider.FONEPAY)
        password, hmac_key = _secrets(credential)
        username = credential.extra.get("username", "")
        prn = str(payment.transaction_uuid)
        amount = f"{payment.amount_npr:.2f}"
        remarks1 = f"FitKhata {payment.member.member_code}"
        remarks2 = "Membership payment"

        signature = _sign(hmac_key, amount, prn, credential.merchant_code, remarks1, remarks2)

        response = requests.post(
            f"{BASE_URL[credential.environment]}{QR_DOWNLOAD_PATH}",
            json={
                "amount": amount,
                "remarks1": remarks1,
                "remarks2": remarks2,
                "prn": prn,
                "merchantCode": credential.merchant_code,
                "username": username,
                "password": password,
                "dataValidation": signature,
            },
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()
        if not data.get("success"):
            raise GatewayVerificationFailed(f"Fonepay QR generation failed: {data.get('message')}")

        # Not a redirect URL — the "url" field here carries the raw QR
        # payload for the desk UI to render as a QR code image itself.
        return RedirectInstructions(
            url=data["qrMessage"],
            method="GET",
            fields={"websocket_url": data.get("thirdpartyQrWebSocketUrl", "")},
        )

    def verify(self, callback_data: dict[str, Any]) -> VerifiedResult:
        """callback_data = {"prn": str, "gym": Gym} — a status poll, not a
        signed callback (Fonepay's own push channel is the websocket URL
        handed back by initiate(); this is the Celery Beat re-verification
        task's fallback path for FR-4.5-style polling).
        """
        gym = callback_data["gym"]
        prn = callback_data["prn"]
        credential = resolve_credential(gym, GatewayCredential.Provider.FONEPAY)
        password, hmac_key = _secrets(credential)
        username = credential.extra.get("username", "")

        signature = _sign(hmac_key, prn, credential.merchant_code)
        response = requests.post(
            f"{BASE_URL[credential.environment]}{QR_STATUS_PATH}",
            json={
                "prn": prn,
                "merchantCode": credential.merchant_code,
                "username": username,
                "password": password,
                "dataValidation": signature,
            },
            timeout=15,
        )
        response.raise_for_status()
        result = response.json()

        completed = result.get("paymentStatus") == "success"
        return VerifiedResult(
            completed=completed,
            gateway_ref=result.get("fonepayTraceId", ""),
            raw_response=result,
        )
