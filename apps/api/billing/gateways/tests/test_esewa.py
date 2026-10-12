from __future__ import annotations

import base64
import json
import uuid
from decimal import Decimal
from unittest.mock import Mock, patch

import pytest

from billing.gateways.base import GatewayVerificationFailed
from billing.gateways.esewa import EsewaGateway, _hmac_b64, _sign
from billing.models import GatewayCredential, Payment
from core.context import system_context
from core.crypto import encrypt_bytes
from gyms.models import Gym, Organization
from members.models import Member

pytestmark = pytest.mark.django_db

# Verified against eSewa's own published sample form (developer.esewa.com.np
# /pages/Epay) — total_amount="110", transaction_uuid="241028",
# product_code="EPAYTEST" with the public UAT secret "8gBm/:&EnhH.1/q"
# reproduces exactly this signature. Not a value I invented.
UAT_SECRET = "8gBm/:&EnhH.1/q"
KNOWN_VECTOR_SIGNATURE = "i94zsd3oXF6ZsSr/kGqT4sSzYQzjj1W/waxjWyRwaME="


def test_sign_matches_esewas_own_published_example():
    assert _sign(UAT_SECRET, "110", "241028", "EPAYTEST") == KNOWN_VECTOR_SIGNATURE


def test_sign_changes_with_any_input():
    base = _sign(UAT_SECRET, "100", "abc", "EPAYTEST")
    assert _sign(UAT_SECRET, "101", "abc", "EPAYTEST") != base
    assert _sign(UAT_SECRET, "100", "abd", "EPAYTEST") != base
    assert _sign(UAT_SECRET, "100", "abc", "OTHER") != base


@pytest.fixture
def gym():
    with system_context():
        org = Organization.objects.create(name="Esewa Test Org")
        return Gym.objects.create(org=org, code="ESW1", name="Esewa Test Gym")


@pytest.fixture
def credential(gym):
    with system_context():
        return GatewayCredential.objects.create(
            org=gym.org,
            gym=gym,
            provider=GatewayCredential.Provider.ESEWA,
            environment=GatewayCredential.Environment.SANDBOX,
            merchant_code="EPAYTEST",
            secret_encrypted=encrypt_bytes(UAT_SECRET.encode("utf-8")),
        )


@pytest.fixture
def member(gym):
    with system_context():
        return Member.objects.create(
            org=gym.org,
            gym=gym,
            member_code="ESW1-0001",
            full_name="Test Member",
            phone="+9779800000001",
            qr_secret=b"fixture-not-a-real-secret",
        )


@pytest.fixture
def payment(gym, member):
    with system_context():
        return Payment.objects.create(
            org=gym.org,
            gym=gym,
            member=member,
            mode=Payment.Mode.ESEWA,
            channel=Payment.Channel.ONLINE,
            transaction_uuid=uuid.uuid4(),
            amount_npr=Decimal("3000.00"),
            status=Payment.Status.PENDING,
        )


def test_initiate_builds_a_validly_signed_form(gym, credential, payment):
    with system_context():
        instructions = EsewaGateway().initiate(payment, return_url="https://m.fitkhata.test/pay")

    assert instructions.method == "POST"
    fields = instructions.fields
    assert fields["product_code"] == "EPAYTEST"
    assert fields["total_amount"] == f"{payment.amount_npr:.2f}"
    assert fields["transaction_uuid"] == str(payment.transaction_uuid)
    expected_signature = _sign(
        UAT_SECRET, fields["total_amount"], fields["transaction_uuid"], "EPAYTEST"
    )
    assert fields["signature"] == expected_signature


RESPONSE_FIELD_ORDER = "status,total_amount,transaction_uuid,product_code"


def _encode_callback(
    secret: str, total_amount: str, transaction_uuid: str, status: str
) -> str:
    """Builds a self-consistent (correctly signed) eSewa-style callback
    blob — the signature always matches the given fields, same as a real
    response would. For a deliberately *tampered* blob (real signature,
    altered claim), build the payload dict by hand instead.
    """
    payload = {
        "transaction_code": "ABC123",
        "status": status,
        "total_amount": total_amount,
        "transaction_uuid": transaction_uuid,
        "product_code": "EPAYTEST",
        "signed_field_names": RESPONSE_FIELD_ORDER,
    }
    message = ",".join(f"{field}={payload[field]}" for field in RESPONSE_FIELD_ORDER.split(","))
    payload["signature"] = _hmac_b64(secret, message)
    return base64.b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")


def test_verify_rejects_a_tampered_signature(gym, credential, payment):
    with system_context():
        # A genuine signature for a *different* amount, pasted onto a
        # claim of 100000 — exactly the tampering rule 6 exists to catch.
        # Fails at the signature step regardless of which payment is
        # passed, so `payment` here doesn't need to match these values.
        transaction_uuid = str(payment.transaction_uuid)
        real_message = (
            f"status=COMPLETE,total_amount=100.00,"
            f"transaction_uuid={transaction_uuid},product_code=EPAYTEST"
        )
        real_signature = _hmac_b64(UAT_SECRET, real_message)
        payload = {
            "transaction_code": "ABC123",
            "status": "COMPLETE",
            "total_amount": "100000.00",  # tampered — signature below is for 100.00
            "transaction_uuid": transaction_uuid,
            "product_code": "EPAYTEST",
            "signed_field_names": RESPONSE_FIELD_ORDER,
            "signature": real_signature,
        }
        data = base64.b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")

        with pytest.raises(GatewayVerificationFailed, match="signature"):
            EsewaGateway().verify({"data": data, "gym": gym, "payment": payment})


def test_verify_rejects_missing_required_signed_fields(gym, credential, payment):
    with system_context():
        signature = _sign(
            UAT_SECRET, f"{payment.amount_npr:.2f}", str(payment.transaction_uuid), "EPAYTEST"
        )
        payload = {
            "status": "COMPLETE",
            "total_amount": f"{payment.amount_npr:.2f}",
            "transaction_uuid": str(payment.transaction_uuid),
            "product_code": "EPAYTEST",
            # Missing "status" from the signed set — eSewa's own protocol
            # names which fields it signed; a response that doesn't even
            # claim to sign `status` can't be trusted to tell us it's
            # really COMPLETE.
            "signed_field_names": "total_amount,transaction_uuid,product_code",
            "signature": signature,
        }
        data = base64.b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")

        with pytest.raises(GatewayVerificationFailed, match="signed_field_names"):
            EsewaGateway().verify({"data": data, "gym": gym, "payment": payment})


def test_verify_uses_the_responses_own_signed_field_order(gym, credential, payment):
    """The response's signed message is built from whatever field list
    signed_field_names gives — not a hardcoded assumption that it's always
    the request's 3-field formula. A 6-field order (closer to what eSewa's
    real response actually signs over) must verify correctly too.
    """
    with system_context():
        total_amount = f"{payment.amount_npr:.2f}"
        transaction_uuid = str(payment.transaction_uuid)
        field_names = (
            "transaction_code,status,total_amount,transaction_uuid,"
            "product_code,signed_field_names"
        )
        message = (
            f"transaction_code=ABC123,status=COMPLETE,total_amount={total_amount},"
            f"transaction_uuid={transaction_uuid},product_code=EPAYTEST,"
            f"signed_field_names={field_names}"
        )
        signature = _hmac_b64(UAT_SECRET, message)
        payload = {
            "transaction_code": "ABC123",
            "status": "COMPLETE",
            "total_amount": total_amount,
            "transaction_uuid": transaction_uuid,
            "product_code": "EPAYTEST",
            "signed_field_names": field_names,
            "signature": signature,
        }
        data = base64.b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")

        mock_response = Mock()
        mock_response.json.return_value = {"status": "COMPLETE", "ref_id": "REF-6FIELD"}
        mock_response.raise_for_status.return_value = None

        with patch("billing.gateways.esewa.requests.get", return_value=mock_response):
            result = EsewaGateway().verify({"data": data, "gym": gym, "payment": payment})

    assert result.completed is True
    assert result.gateway_ref == "REF-6FIELD"


def test_verify_returns_not_completed_for_a_non_complete_status(gym, credential, payment):
    with system_context():
        total_amount = f"{payment.amount_npr:.2f}"
        transaction_uuid = str(payment.transaction_uuid)
        data = _encode_callback(UAT_SECRET, total_amount, transaction_uuid, "PENDING")

        result = EsewaGateway().verify({"data": data, "gym": gym, "payment": payment})

    assert result.completed is False


def test_verify_confirms_against_the_status_check_api_when_signature_is_valid(
    gym, credential, payment
):
    with system_context():
        total_amount = f"{payment.amount_npr:.2f}"
        transaction_uuid = str(payment.transaction_uuid)
        data = _encode_callback(UAT_SECRET, total_amount, transaction_uuid, "COMPLETE")

        mock_response = Mock()
        mock_response.json.return_value = {"status": "COMPLETE", "ref_id": "REF-999"}
        mock_response.raise_for_status.return_value = None

        with patch("billing.gateways.esewa.requests.get", return_value=mock_response) as mock_get:
            result = EsewaGateway().verify({"data": data, "gym": gym, "payment": payment})

    assert result.completed is True
    assert result.gateway_ref == "REF-999"
    mock_get.assert_called_once()


def test_verify_rejects_a_swapped_payment(gym, credential, member):
    """The receipt-swap attack: a genuinely-signed callback for a
    completed small payment (A) must not be usable to complete a
    different, larger payment (B) just because B's payment_id was passed
    alongside A's blob — verify() must check the blob's own
    transaction_uuid/total_amount against the SPECIFIC payment it's being
    asked to confirm, not just that the blob is internally consistent.
    """
    with system_context():
        payment_a = Payment.objects.create(
            org=gym.org,
            gym=gym,
            member=member,
            mode=Payment.Mode.ESEWA,
            channel=Payment.Channel.ONLINE,
            transaction_uuid=uuid.uuid4(),
            amount_npr=Decimal("10.00"),
            status=Payment.Status.PENDING,
        )
        payment_b = Payment.objects.create(
            org=gym.org,
            gym=gym,
            member=member,
            mode=Payment.Mode.ESEWA,
            channel=Payment.Channel.ONLINE,
            transaction_uuid=uuid.uuid4(),
            amount_npr=Decimal("19990.00"),
            status=Payment.Status.PENDING,
        )

        # A real, validly-signed callback for payment_a's own amount/uuid —
        # eSewa's status API would truthfully confirm IT (not payment_b),
        # which is exactly why relying on it alone is the bug.
        data = _encode_callback(UAT_SECRET, "10.00", str(payment_a.transaction_uuid), "COMPLETE")

        mock_response = Mock()
        mock_response.json.return_value = {"status": "COMPLETE", "ref_id": "REF-SWAP"}
        mock_response.raise_for_status.return_value = None

        with patch("billing.gateways.esewa.requests.get", return_value=mock_response):
            with pytest.raises(GatewayVerificationFailed):
                EsewaGateway().verify({"data": data, "gym": gym, "payment": payment_b})


def test_verify_rejects_an_amount_mismatch_against_the_payment(gym, credential, payment):
    with system_context():
        transaction_uuid = str(payment.transaction_uuid)
        # Genuinely signed, but for a different amount than this payment's.
        data = _encode_callback(UAT_SECRET, "1.00", transaction_uuid, "COMPLETE")

        with pytest.raises(GatewayVerificationFailed, match="amount"):
            EsewaGateway().verify({"data": data, "gym": gym, "payment": payment})


def test_verify_rejects_a_product_code_mismatch(gym, credential, payment):
    with system_context():
        total_amount = f"{payment.amount_npr:.2f}"
        transaction_uuid = str(payment.transaction_uuid)
        payload = {
            "transaction_code": "ABC123",
            "status": "COMPLETE",
            "total_amount": total_amount,
            "transaction_uuid": transaction_uuid,
            "product_code": "SOMEONE-ELSES-MERCHANT",
            "signed_field_names": RESPONSE_FIELD_ORDER,
        }
        message = ",".join(f"{field}={payload[field]}" for field in RESPONSE_FIELD_ORDER.split(","))
        payload["signature"] = _hmac_b64(UAT_SECRET, message)
        data = base64.b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")

        with pytest.raises(GatewayVerificationFailed, match="product_code"):
            EsewaGateway().verify({"data": data, "gym": gym, "payment": payment})


def test_verify_rejects_completion_if_status_check_disagrees(gym, credential, payment):
    """Signature valid, callback claims COMPLETE — but the status-check API
    (the actual source of truth) says otherwise. Must not trust the
    redirect payload alone.
    """
    with system_context():
        total_amount = f"{payment.amount_npr:.2f}"
        transaction_uuid = str(payment.transaction_uuid)
        data = _encode_callback(UAT_SECRET, total_amount, transaction_uuid, "COMPLETE")

        mock_response = Mock()
        mock_response.json.return_value = {"status": "AMBIGUOUS"}
        mock_response.raise_for_status.return_value = None

        with patch("billing.gateways.esewa.requests.get", return_value=mock_response):
            result = EsewaGateway().verify({"data": data, "gym": gym, "payment": payment})

    assert result.completed is False
