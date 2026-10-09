from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.utils import timezone

from billing.gateways.base import VerifiedResult
from billing.models import GatewayCredential, Invoice, Payment
from billing.services import collect_payment
from billing.tasks import reverify_pending_payments
from core.context import system_context
from core.crypto import encrypt_bytes
from gyms.models import Gym, Organization
from members.models import Member, Plan
from members.services import initiate_renewal_payment

pytestmark = pytest.mark.django_db

STALE_CUTOFF_MINUTES = 15


@pytest.fixture
def gym():
    with system_context():
        org = Organization.objects.create(name="Reverify Test Org")
        return Gym.objects.create(org=org, code="RVF1", name="Reverify Test Gym")


@pytest.fixture
def plan(gym):
    with system_context():
        return Plan.objects.create(
            org=gym.org, gym=gym, name="Monthly", duration_days=30, price_npr=Decimal("3000.00")
        )


@pytest.fixture
def member(gym):
    with system_context():
        return Member.objects.create(
            org=gym.org,
            gym=gym,
            member_code="RVF1-0001",
            full_name="Test Member",
            phone="+9779800000001",
            qr_secret=b"fixture-not-a-real-secret",
        )


def _backdate(payment: Payment, minutes: int) -> None:
    Payment.objects.filter(pk=payment.pk).update(
        created_at=timezone.now() - timedelta(minutes=minutes)
    )


def _esewa_credential(gym):
    return GatewayCredential.objects.create(
        org=gym.org,
        gym=gym,
        provider=GatewayCredential.Provider.ESEWA,
        merchant_code="EPAYTEST",
        secret_encrypted=encrypt_bytes(b"fixture-secret"),
    )


def _khalti_credential(gym):
    return GatewayCredential.objects.create(
        org=gym.org,
        gym=gym,
        provider=GatewayCredential.Provider.KHALTI,
        merchant_code="",
        secret_encrypted=encrypt_bytes(b"fixture-secret"),
    )


def test_ignores_payments_younger_than_the_stale_cutoff(gym, plan, member):
    with system_context():
        _esewa_credential(gym)
        initiate_renewal_payment(member, plan, "esewa")
        # Not backdated — still fresh.

        with patch("billing.tasks.EsewaGateway") as mock_gateway_cls:
            confirmed = reverify_pending_payments()

    assert confirmed == 0
    mock_gateway_cls.assert_not_called()


def test_confirms_a_stale_esewa_payment_and_issues_its_invoice(gym, plan, member):
    with system_context():
        _esewa_credential(gym)
        payment = initiate_renewal_payment(member, plan, "esewa")
        _backdate(payment, STALE_CUTOFF_MINUTES + 1)

        fake_result = VerifiedResult(completed=True, gateway_ref="REF-1", raw_response={})
        with patch(
            "billing.tasks.EsewaGateway.check_status", return_value=fake_result
        ):
            confirmed = reverify_pending_payments()

        payment.refresh_from_db()
        assert confirmed == 1
        assert payment.status == Payment.Status.COMPLETED
        assert payment.invoice.status == Invoice.Status.ISSUED


def test_leaves_a_stale_esewa_payment_pending_if_still_not_complete(gym, plan, member):
    with system_context():
        _esewa_credential(gym)
        payment = initiate_renewal_payment(member, plan, "esewa")
        _backdate(payment, STALE_CUTOFF_MINUTES + 1)

        fake_result = VerifiedResult(completed=False, gateway_ref="", raw_response={})
        with patch("billing.tasks.EsewaGateway.check_status", return_value=fake_result):
            confirmed = reverify_pending_payments()

        payment.refresh_from_db()

    assert confirmed == 0
    assert payment.status == Payment.Status.PENDING


def test_confirms_a_stale_khalti_payment_using_its_stored_pidx(gym, plan, member):
    with system_context():
        _khalti_credential(gym)
        payment = initiate_renewal_payment(member, plan, "khalti")
        payment.gateway_ref = "pidx-abc123"
        payment.save(update_fields=["gateway_ref"])
        _backdate(payment, STALE_CUTOFF_MINUTES + 1)

        fake_result = VerifiedResult(completed=True, gateway_ref="txn-1", raw_response={})
        with patch("billing.tasks.KhaltiGateway.verify", return_value=fake_result) as mock_verify:
            confirmed = reverify_pending_payments()

        payment.refresh_from_db()

    assert confirmed == 1
    assert payment.status == Payment.Status.COMPLETED
    mock_verify.assert_called_once()
    call_arg = mock_verify.call_args.args[0]
    assert call_arg["pidx"] == "pidx-abc123"


def test_skips_a_khalti_payment_with_no_pidx_without_erroring(gym, plan, member):
    with system_context():
        _khalti_credential(gym)
        payment = initiate_renewal_payment(member, plan, "khalti")
        # No gateway_ref set — initiate() was never actually called against
        # the real API in this test, so there's no pidx to look up yet.
        _backdate(payment, STALE_CUTOFF_MINUTES + 1)

        confirmed = reverify_pending_payments()
        payment.refresh_from_db()

    assert confirmed == 0
    assert payment.status == Payment.Status.PENDING


def test_skips_a_payment_with_no_configured_credential(gym, plan, member):
    with system_context():
        # No GatewayCredential created for this gym at all.
        payment = initiate_renewal_payment(member, plan, "esewa")
        _backdate(payment, STALE_CUTOFF_MINUTES + 1)

        confirmed = reverify_pending_payments()
        payment.refresh_from_db()

    assert confirmed == 0
    assert payment.status == Payment.Status.PENDING


def test_replay_safe_if_already_completed_by_the_time_the_task_runs(gym, plan, member):
    """A payment confirmed through the normal callback path moments before
    the beat task picks it up must not be double-processed.
    """
    with system_context():
        _esewa_credential(gym)
        payment = initiate_renewal_payment(member, plan, "esewa")
        _backdate(payment, STALE_CUTOFF_MINUTES + 1)
        collect_payment(payment, gateway_ref="REF-already-done")

        fake_result = VerifiedResult(completed=True, gateway_ref="REF-2", raw_response={})
        with patch("billing.tasks.EsewaGateway.check_status", return_value=fake_result):
            confirmed = reverify_pending_payments()

    # The task's own query only selects status=pending, so an
    # already-completed payment is never even considered.
    assert confirmed == 0
