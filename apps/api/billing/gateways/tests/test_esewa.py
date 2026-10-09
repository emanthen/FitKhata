from __future__ import annotations

import base64
import json
import uuid
from decimal import Decimal
from unittest.mock import Mock, patch

import pytest

from billing.gateways.base import GatewayVerificationFailed
from billing.gateways.esewa import EsewaGateway, _sign
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


def _encode_callback(total_amount: str, transaction_uuid: str, status: str, signature: str) -> str:
    payload = {
        "transaction_code": "ABC123",
        "status": status,
        "total_amount": total_amount,
        "transaction_uuid": transaction_uuid,
        "product_code": "EPAYTEST",
        "signed_field_names": "total_amount,transaction_uuid,product_code",
        "signature": signature,
    }
    return base64.b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")


def test_verify_rejects_a_tampered_signature(gym, credential):
    with system_context():
        # A genuine signature for a *different* amount, pasted onto a
        # claim of 100000 — exactly the tampering rule 6 exists to catch.
        real_signature = _sign(UAT_SECRET, "100.00", "tx-1", "EPAYTEST")
        data = _encode_callback("100000.00", "tx-1", "COMPLETE", real_signature)

        with pytest.raises(GatewayVerificationFailed, match="signature"):
            EsewaGateway().verify({"data": data, "gym": gym})


def test_verify_returns_not_completed_for_a_non_complete_status(gym, credential):
    with system_context():
        signature = _sign(UAT_SECRET, "100.00", "tx-2", "EPAYTEST")
        data = _encode_callback("100.00", "tx-2", "PENDING", signature)

        result = EsewaGateway().verify({"data": data, "gym": gym})

    assert result.completed is False


def test_verify_confirms_against_the_status_check_api_when_signature_is_valid(gym, credential):
    with system_context():
        signature = _sign(UAT_SECRET, "100.00", "tx-3", "EPAYTEST")
        data = _encode_callback("100.00", "tx-3", "COMPLETE", signature)

        mock_response = Mock()
        mock_response.json.return_value = {"status": "COMPLETE", "ref_id": "REF-999"}
        mock_response.raise_for_status.return_value = None

        with patch("billing.gateways.esewa.requests.get", return_value=mock_response) as mock_get:
            result = EsewaGateway().verify({"data": data, "gym": gym})

    assert result.completed is True
    assert result.gateway_ref == "REF-999"
    mock_get.assert_called_once()


def test_verify_rejects_completion_if_status_check_disagrees(gym, credential):
    """Signature valid, callback claims COMPLETE — but the status-check API
    (the actual source of truth) says otherwise. Must not trust the
    redirect payload alone.
    """
    with system_context():
        signature = _sign(UAT_SECRET, "100.00", "tx-4", "EPAYTEST")
        data = _encode_callback("100.00", "tx-4", "COMPLETE", signature)

        mock_response = Mock()
        mock_response.json.return_value = {"status": "AMBIGUOUS"}
        mock_response.raise_for_status.return_value = None

        with patch("billing.gateways.esewa.requests.get", return_value=mock_response):
            result = EsewaGateway().verify({"data": data, "gym": gym})

    assert result.completed is False
