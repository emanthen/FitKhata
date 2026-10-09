from __future__ import annotations

import uuid
from decimal import Decimal
from unittest.mock import Mock, patch

import pytest

from billing.gateways.base import GatewayVerificationFailed
from billing.gateways.khalti import KhaltiGateway, _amount_paisa
from billing.models import GatewayCredential, Payment
from core.context import system_context
from core.crypto import encrypt_bytes
from gyms.models import Gym, Organization
from members.models import Member

pytestmark = pytest.mark.django_db

TEST_SECRET = "test_secret_key_fixture_only"


def test_amount_paisa_converts_rupees_to_integer_paisa():
    assert _amount_paisa(Decimal("3000.00")) == 300_000
    assert _amount_paisa(Decimal("29.99")) == 2_999


@pytest.fixture
def gym():
    with system_context():
        org = Organization.objects.create(name="Khalti Test Org")
        return Gym.objects.create(org=org, code="KHL1", name="Khalti Test Gym")


@pytest.fixture
def credential(gym):
    with system_context():
        return GatewayCredential.objects.create(
            org=gym.org,
            gym=gym,
            provider=GatewayCredential.Provider.KHALTI,
            environment=GatewayCredential.Environment.SANDBOX,
            merchant_code="",
            secret_encrypted=encrypt_bytes(TEST_SECRET.encode("utf-8")),
        )


@pytest.fixture
def member(gym):
    with system_context():
        return Member.objects.create(
            org=gym.org,
            gym=gym,
            member_code="KHL1-0001",
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
            mode=Payment.Mode.KHALTI,
            channel=Payment.Channel.ONLINE,
            transaction_uuid=uuid.uuid4(),
            amount_npr=Decimal("3000.00"),
            status=Payment.Status.PENDING,
        )


def test_initiate_posts_the_right_fields_and_auth_header(gym, credential, payment):
    mock_response = Mock()
    mock_response.json.return_value = {
        "pidx": "abc123",
        "payment_url": "https://test-pay.khalti.com/?pidx=abc123",
    }
    mock_response.raise_for_status.return_value = None

    with system_context():
        with patch(
            "billing.gateways.khalti.requests.post", return_value=mock_response
        ) as mock_post:
            instructions = KhaltiGateway().initiate(
                payment, return_url="https://m.fitkhata.test/pay"
            )

    assert instructions.method == "GET"
    assert instructions.url == "https://test-pay.khalti.com/?pidx=abc123"
    call_kwargs = mock_post.call_args.kwargs
    assert call_kwargs["headers"]["Authorization"] == f"Key {TEST_SECRET}"
    assert call_kwargs["json"]["amount"] == 300_000
    assert call_kwargs["json"]["purchase_order_id"] == str(payment.transaction_uuid)


def test_verify_accepts_completed_status_with_matching_amount(gym, credential):
    mock_response = Mock()
    mock_response.json.return_value = {
        "status": "Completed",
        "total_amount": 300_000,
        "transaction_id": "txn-1",
    }
    mock_response.raise_for_status.return_value = None

    with system_context():
        with patch("billing.gateways.khalti.requests.post", return_value=mock_response):
            result = KhaltiGateway().verify(
                {"pidx": "abc123", "gym": gym, "expected_amount_paisa": 300_000}
            )

    assert result.completed is True
    assert result.gateway_ref == "txn-1"


def test_verify_rejects_completed_status_with_mismatched_amount(gym, credential):
    """A tampered/mismatched pidx claiming a different amount than what
    this payment was actually initiated for must never proceed.
    """
    mock_response = Mock()
    mock_response.json.return_value = {"status": "Completed", "total_amount": 1}
    mock_response.raise_for_status.return_value = None

    with system_context():
        with patch("billing.gateways.khalti.requests.post", return_value=mock_response):
            with pytest.raises(GatewayVerificationFailed, match="amount mismatch"):
                KhaltiGateway().verify(
                    {"pidx": "abc123", "gym": gym, "expected_amount_paisa": 300_000}
                )


def test_verify_returns_not_completed_for_pending_status(gym, credential):
    mock_response = Mock()
    mock_response.json.return_value = {"status": "Pending", "total_amount": 300_000}
    mock_response.raise_for_status.return_value = None

    with system_context():
        with patch("billing.gateways.khalti.requests.post", return_value=mock_response):
            result = KhaltiGateway().verify(
                {"pidx": "abc123", "gym": gym, "expected_amount_paisa": 300_000}
            )

    assert result.completed is False
