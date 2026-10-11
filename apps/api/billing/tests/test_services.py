from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest

from billing.models import Invoice, Payment
from billing.services import (
    InvoiceLineInput,
    collect_payment,
    create_draft_invoice,
    outstanding_dues_npr,
)
from core.context import system_context
from gyms.models import Gym, Organization
from members.models import Member, Membership, Plan
from members.services import fulfill_renewal_payment, initiate_renewal_payment, sell_membership

pytestmark = pytest.mark.django_db


@pytest.fixture
def gym():
    with system_context():
        org = Organization.objects.create(name="Billing Test Org")
        return Gym.objects.create(org=org, code="BILL1", name="Billing Test Gym")


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
            member_code="BILL1-0001",
            full_name="Test Member",
            phone="+9779800000001",
            qr_secret=b"not-a-real-secret-just-fixture-bytes",
        )


def _desk_payment(member, invoice, amount: Decimal, status=Payment.Status.PENDING) -> Payment:
    return Payment.objects.create(
        org=member.org,
        gym=member.gym,
        member=member,
        invoice=invoice,
        mode=Payment.Mode.CASH,
        channel=Payment.Channel.DESK,
        transaction_uuid=uuid.uuid4(),
        amount_npr=amount,
        status=status,
    )


# --- create_draft_invoice: VAT split ----------------------------------------
# billing.domain.vat's split functions were fully built and unit-tested in
# isolation but never actually wired into invoice creation -- every invoice
# carried taxable_npr=vat_npr=0 regardless of org VAT settings. These guard
# the fix.


def test_create_draft_invoice_leaves_taxable_equal_to_total_when_not_vat_registered(
    gym, member
):
    with system_context():
        assert gym.org.is_vat_registered is False  # fixture default
        invoice = create_draft_invoice(
            gym,
            member,
            [InvoiceLineInput("Item", 1, Decimal("1000.00"), Decimal("1000.00"))],
            Decimal("1000.00"),
            Decimal("0.00"),
            Decimal("1000.00"),
        )

    assert invoice.taxable_npr == Decimal("1000.00")
    assert invoice.vat_npr == Decimal("0.00")


def test_create_draft_invoice_splits_vat_from_the_total_when_vat_registered(gym, member):
    with system_context():
        gym.org.is_vat_registered = True
        gym.org.save(update_fields=["is_vat_registered"])

        invoice = create_draft_invoice(
            gym,
            member,
            [InvoiceLineInput("Item", 1, Decimal("1130.00"), Decimal("1130.00"))],
            Decimal("1130.00"),
            Decimal("0.00"),
            Decimal("1130.00"),
        )

    assert invoice.taxable_npr == Decimal("1000.00")
    assert invoice.vat_npr == Decimal("130.00")
    assert invoice.taxable_npr + invoice.vat_npr == invoice.total_npr


def test_create_draft_invoice_vat_split_always_reconstructs_the_total(gym, member):
    """taxable_npr + vat_npr must equal total_npr exactly -- total_npr is
    the one real amount already collected (what Payment.amount_npr must
    match), so the split can never report more or less than that, whatever
    the org's vat_inclusive_pricing display setting says (see
    create_draft_invoice's own docstring on why that setting has no effect
    here yet).
    """
    with system_context():
        gym.org.is_vat_registered = True
        gym.org.vat_inclusive_pricing = False
        gym.org.save(update_fields=["is_vat_registered", "vat_inclusive_pricing"])

        invoice = create_draft_invoice(
            gym,
            member,
            [InvoiceLineInput("Item", 1, Decimal("1000.00"), Decimal("1000.00"))],
            Decimal("1000.00"),
            Decimal("0.00"),
            Decimal("1000.00"),
        )

    assert invoice.taxable_npr + invoice.vat_npr == invoice.total_npr


def test_create_draft_invoice_vat_is_split_from_the_post_discount_total(gym, member):
    """A discount reduces the taxable base -- VAT is split from total_npr
    (already post-discount), never from the pre-discount subtotal.
    """
    with system_context():
        gym.org.is_vat_registered = True
        gym.org.save(update_fields=["is_vat_registered"])

        invoice = create_draft_invoice(
            gym,
            member,
            [InvoiceLineInput("Item", 1, Decimal("1130.00"), Decimal("1130.00"))],
            Decimal("1130.00"),  # subtotal (pre-discount)
            Decimal("226.00"),  # discount (20% off)
            Decimal("904.00"),  # total (post-discount) -- VAT splits from this
        )

    assert invoice.taxable_npr == Decimal("800.00")
    assert invoice.vat_npr == Decimal("104.00")
    assert invoice.taxable_npr + invoice.vat_npr == invoice.total_npr


# --- collect_payment: desk flow (invoice already exists) -------------------


def test_collect_payment_marks_completed(gym, plan, member):
    with system_context():
        membership = sell_membership(member, plan, today=date(2026, 1, 1))
        payment = _desk_payment(member, membership.invoice, Decimal("3000.00"))

        result = collect_payment(payment)

    assert result.status == Payment.Status.COMPLETED


def test_collect_payment_issues_invoice_once_fully_paid(gym, plan, member):
    with system_context():
        membership = sell_membership(member, plan, today=date(2026, 1, 1))
        payment = _desk_payment(member, membership.invoice, Decimal("3000.00"))

        collect_payment(payment)
        membership.invoice.refresh_from_db()

    assert membership.invoice.status == Invoice.Status.ISSUED


def test_collect_payment_partial_payment_does_not_issue_invoice(gym, plan, member):
    with system_context():
        membership = sell_membership(member, plan, today=date(2026, 1, 1))
        payment = _desk_payment(member, membership.invoice, Decimal("1000.00"))

        collect_payment(payment)
        membership.invoice.refresh_from_db()

    assert membership.invoice.status == Invoice.Status.DRAFT


def test_collect_payment_issues_after_two_partial_payments_cover_the_total(gym, plan, member):
    with system_context():
        membership = sell_membership(member, plan, today=date(2026, 1, 1))
        first = _desk_payment(member, membership.invoice, Decimal("1000.00"))
        second = _desk_payment(member, membership.invoice, Decimal("2000.00"))

        collect_payment(first)
        membership.invoice.refresh_from_db()
        assert membership.invoice.status == Invoice.Status.DRAFT

        collect_payment(second)
        membership.invoice.refresh_from_db()

    assert membership.invoice.status == Invoice.Status.ISSUED


def test_collect_payment_is_idempotent_on_replay(gym, plan, member):
    """Rule 6: a replayed confirmation is a no-op, not a double-count."""
    with system_context():
        membership = sell_membership(member, plan, today=date(2026, 1, 1))
        payment = _desk_payment(member, membership.invoice, Decimal("3000.00"))

        first = collect_payment(payment)
        second = collect_payment(payment)

        assert first.status == second.status == Payment.Status.COMPLETED
        # Only one payment row exists either way — replaying collect_payment
        # on the same row can't duplicate it; this pins that down explicitly.
        assert Payment.objects.filter(invoice=membership.invoice).count() == 1


def test_outstanding_dues_npr_reflects_partial_payment(gym, plan, member):
    with system_context():
        membership = sell_membership(member, plan, today=date(2026, 1, 1))
        payment = _desk_payment(member, membership.invoice, Decimal("1200.00"))
        collect_payment(payment)
        membership.invoice.refresh_from_db()

        dues = outstanding_dues_npr(membership.invoice)

    assert dues == Decimal("1800.00")


# --- collect_payment: online renewal flow (membership doesn't exist yet) --


def test_initiate_renewal_payment_does_not_create_a_membership(gym, plan, member):
    with system_context():
        payment = initiate_renewal_payment(member, plan, "esewa", today=date(2026, 1, 1))

    assert payment.status == Payment.Status.PENDING
    assert payment.invoice.status == Invoice.Status.DRAFT
    assert member.memberships.count() == 0


def test_collect_payment_fulfills_renewal_and_creates_membership(gym, plan, member):
    with system_context():
        payment = initiate_renewal_payment(member, plan, "esewa", today=date(2026, 1, 1))
        collect_payment(payment)
        payment.invoice.refresh_from_db()

        assert payment.invoice.status == Invoice.Status.ISSUED
        assert Membership.objects.filter(member=member).count() == 1
        membership = Membership.objects.get(member=member)
        assert membership.start_date == date(2026, 1, 1)
        assert membership.expiry_date == date(2026, 1, 30)
        assert membership.invoice_id == payment.invoice_id


def test_replayed_renewal_callback_creates_no_second_membership(gym, plan, member):
    """The spec's own acceptance criterion: a replayed gateway callback
    must not double-fulfill a renewal.
    """
    with system_context():
        payment = initiate_renewal_payment(member, plan, "esewa", today=date(2026, 1, 1))
        collect_payment(payment)
        collect_payment(payment)  # simulated duplicate callback delivery

        assert Membership.objects.filter(member=member).count() == 1


def test_fulfill_renewal_payment_applies_promo_and_tracks_redemption(gym, plan, member):
    from members.models import PromoCode

    with system_context():
        promo = PromoCode.objects.create(
            org=gym.org,
            gym=gym,
            code="RENEW150",
            kind="flat",
            value=Decimal("150.00"),
            valid_from=date(2026, 1, 1),
            valid_to=date(2026, 12, 31),
        )
        payment = initiate_renewal_payment(
            member, plan, "khalti", promo=promo, today=date(2026, 1, 1)
        )
        collect_payment(payment)
        promo.refresh_from_db()

        assert payment.invoice.total_npr == Decimal("2850.00")
        assert promo.times_used == 1
        assert member.promo_redemptions.count() == 1


def test_fulfill_renewal_payment_can_be_called_directly(gym, plan, member):
    """fulfill_renewal_payment is also exercised directly here — the
    collect_payment tests above cover it through its real caller, this
    pins down its own contract in isolation.
    """
    with system_context():
        payment = initiate_renewal_payment(member, plan, "esewa", today=date(2026, 1, 1))
        membership = fulfill_renewal_payment(payment)

    assert membership.member_id == member.pk
    assert membership.plan_id == plan.pk
