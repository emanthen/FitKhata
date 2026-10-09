"""Draft-invoice creation (rule 9) and payment confirmation (rules 6/7)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.db.models import Sum

from billing.domain.shift import expected_cash
from billing.models import CashShift, Invoice, InvoiceCounter, InvoiceLine, Payment
from core.domain.bs import to_bs
from core.services import audit
from notifications.services import notify

# Nepali fiscal year runs Shrawan 1 (BS month 4) to the following Asar's end.
# Same rule core.domain.nptime.fiscal_year() uses — duplicated here only
# because that helper returns a "2083/84" display string and this needs the
# bare start-year int for InvoiceCounter/Invoice.fiscal_year.
_FISCAL_YEAR_START_MONTH = 4


def _fiscal_year_for(d: date) -> int:
    bs_year, bs_month, _ = to_bs(d)
    return bs_year if bs_month >= _FISCAL_YEAR_START_MONTH else bs_year - 1


@dataclass
class InvoiceLineInput:
    description: str
    quantity: int
    unit_price_npr: Decimal
    line_total_npr: Decimal


def create_draft_invoice(
    gym: Any,
    member: Any,
    lines: list[InvoiceLineInput],
    subtotal_npr: Decimal,
    discount_npr: Decimal,
    total_npr: Decimal,
    actor: Any = None,
    today: date | None = None,
) -> Invoice:
    """Allocates the next gapless invoice number for (org, fiscal_year)
    under a row lock — rule 8.
    """
    today = today or date.today()
    fiscal_year = _fiscal_year_for(today)

    with transaction.atomic():
        counter, _ = InvoiceCounter.objects.select_for_update().get_or_create(
            org=gym.org, fiscal_year=fiscal_year
        )
        counter.last_value += 1
        counter.save(update_fields=["last_value"])
        number = f"{fiscal_year}-{counter.last_value:05d}"

        bs_year, bs_month, bs_day = to_bs(today)
        invoice = Invoice.objects.create(
            org=gym.org,
            gym=gym,
            number=number,
            fiscal_year=fiscal_year,
            member=member,
            subtotal_npr=subtotal_npr,
            discount_npr=discount_npr,
            total_npr=total_npr,
            bill_date=today,
            bill_date_bs=f"{bs_year:04d}-{bs_month:02d}-{bs_day:02d}",
            buyer_name=member.full_name,
        )
        InvoiceLine.objects.bulk_create(
            InvoiceLine(
                org=gym.org,
                gym=gym,
                invoice=invoice,
                description=line.description,
                quantity=line.quantity,
                unit_price_npr=line.unit_price_npr,
                line_total_npr=line.line_total_npr,
            )
            for line in lines
        )
        audit(invoice, "create", after={"number": number, "total_npr": str(total_npr)}, actor=actor)
        return invoice


def collect_payment(
    payment: Payment,
    *,
    gateway_ref: str = "",
    raw_response: dict | None = None,
    actor: Any = None,
) -> Payment:
    """The single entry point that marks a Payment completed — used by
    both desk collection (cash/manual/bank/cheque, already status=pending
    from the moment it's created) and online gateway callbacks (eSewa/
    Khalti, after their own signature/status verification). Rule 6:
    idempotent on transaction_uuid — select_for_update locks the row, and
    a replay (same payment already completed) is a safe no-op.

    Within the same locked transaction: marks completed -> if this fully
    pays its invoice, issues it -> if that invoice was an online renewal
    with no membership yet, fulfills it (lazy import — see the module
    docstring reasoning below).
    """
    with transaction.atomic():
        locked = Payment.objects.select_for_update().get(pk=payment.pk)
        if locked.status == Payment.Status.COMPLETED:
            return locked

        locked.status = Payment.Status.COMPLETED
        if gateway_ref:
            locked.gateway_ref = gateway_ref
        if raw_response is not None:
            locked.raw_response = raw_response
        locked.save(update_fields=["status", "gateway_ref", "raw_response", "updated_at"])
        audit(locked, "update", after={"status": Payment.Status.COMPLETED}, actor=actor)
        notify(
            locked.member,
            "payment_receipt",
            {
                "name": locked.member.full_name,
                "amount": str(locked.amount_npr),
                "invoice_number": locked.invoice.number if locked.invoice else "",
            },
            actor=actor,
        )

        referrer = locked.member.referred_by
        if referrer is not None and (
            Payment.objects.filter(
                member=locked.member, status=Payment.Status.COMPLETED
            ).count()
            == 1
        ):
            # FR-8.8: reward the referrer on the referred member's first-ever
            # completed payment. Lazy import — same circular-dependency
            # reasoning as the fulfill_renewal_payment import just below.
            from members.services import reward_referral

            reward_referral(referrer, actor=actor)

        invoice = locked.invoice
        if invoice is not None and invoice.status == Invoice.Status.DRAFT:
            paid_total = Payment.objects.filter(
                invoice=invoice, status=Payment.Status.COMPLETED
            ).aggregate(total=Sum("amount_npr"))["total"] or Decimal("0.00")

            if paid_total >= invoice.total_npr:
                invoice.status = Invoice.Status.ISSUED
                invoice.save(update_fields=["status"])
                audit(invoice, "update", after={"status": Invoice.Status.ISSUED}, actor=actor)

                if locked.metadata.get("renewal"):
                    # members/services.py already imports from this module
                    # (create_draft_invoice) — importing it back at module
                    # scope here would be circular. Same lazy-import shape
                    # attendance/services.py uses for its consumers import.
                    from members.services import fulfill_renewal_payment

                    fulfill_renewal_payment(locked, actor=actor)

        return locked


def shift_expected_cash_npr(shift: CashShift) -> Decimal:
    """float + completed cash payments taken during this shift — rule per
    billing/domain/shift.py. No per-shift refund tracking yet this phase,
    so the refunds term is always zero for now.
    """
    cash_payments = Payment.objects.filter(
        shift=shift, status=Payment.Status.COMPLETED, mode=Payment.Mode.CASH
    ).aggregate(total=Sum("amount_npr"))["total"] or Decimal("0.00")
    return expected_cash(shift.opening_float_npr, cash_payments)


def outstanding_dues_npr(invoice: Invoice) -> Decimal:
    """invoice.total_npr minus whatever's already been collected against
    it — what the FR-4.9 collect-payment drawer shows as still owed, and
    what a partial payment is measured against.
    """
    paid = Payment.objects.filter(
        invoice=invoice, status=Payment.Status.COMPLETED
    ).aggregate(total=Sum("amount_npr"))["total"] or Decimal("0.00")
    return (invoice.total_npr - paid).quantize(Decimal("0.01"))
