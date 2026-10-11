"""Draft-invoice creation (rule 9) and payment confirmation (rules 6/7)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.db.models import Sum

from billing.domain.shift import expected_cash
from billing.domain.vat import vat_for_invoice
from billing.models import (
    CashShift,
    Invoice,
    InvoiceCounter,
    InvoiceLine,
    Payment,
    Product,
    Sale,
    SaleLine,
)
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

    VAT is split off `total_npr` (the post-discount amount the member
    actually owes), not the pre-discount subtotal — a discount reduces the
    taxable base, it isn't layered on top of a VAT figure computed before
    the discount applied. A non-VAT-registered org (gym.org.is_vat_registered
    is False) issues no VAT at all: vat_npr stays zero and the full total
    is taxable in the sense that it's the sale amount, not that any VAT
    line is shown on an invoice from a business that isn't registered for it.

    Always back-splits as if `total_npr` is VAT-inclusive (never adds VAT
    on top of it), regardless of gym.org.vat_inclusive_pricing -- total_npr
    is the one real amount already being collected (what Payment.amount_npr
    must match), so taxable_npr + vat_npr must reconstruct it exactly; using
    vat_for_line(..., inclusive=False) here would report a total 13% larger
    than what was actually charged. Properly honoring "exclusive" pricing
    means adding VAT on top when the subtotal is first computed (plan/
    product prices, in members.domain and this POS's own pricing) before it
    ever reaches this function -- not implemented yet in either caller, so
    gym.org.vat_inclusive_pricing currently has no effect here.
    """
    today = today or date.today()
    fiscal_year = _fiscal_year_for(today)

    if gym.org.is_vat_registered:
        line_vat = vat_for_invoice([total_npr], inclusive=True)
        taxable_npr, vat_npr = line_vat.taxable_npr, line_vat.vat_npr
    else:
        taxable_npr, vat_npr = total_npr, Decimal("0.00")

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
            taxable_npr=taxable_npr,
            vat_npr=vat_npr,
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


@dataclass
class SaleLineInput:
    product_id: int
    quantity: int


class InsufficientStock(ValueError):
    pass


def record_pos_sale(
    gym: Any, member: Any, lines: list[SaleLineInput], actor: Any = None
) -> Sale:
    """FR-12.7: rings up retail stock against a member, through the exact
    same create_draft_invoice() the membership-sale flow uses (rule 8
    numbering, no parallel invoice scheme) -- then records the Sale/
    SaleLine breakdown and decrements stock in the same transaction.
    select_for_update on the Product rows (locked in a stable pk order, not
    request order, to avoid a lock-ordering deadlock between two concurrent
    POS sales that happen to ring up the same two products in opposite
    order) makes the stock check safe under concurrent sales at the same
    till.
    """
    with transaction.atomic():
        product_ids = sorted({line.product_id for line in lines})
        products = {
            p.pk: p
            for p in Product.objects.select_for_update().filter(gym=gym, pk__in=product_ids)
        }

        invoice_lines: list[InvoiceLineInput] = []
        subtotal = Decimal("0.00")
        for line in lines:
            product = products.get(line.product_id)
            if product is None or not product.is_active:
                raise InsufficientStock(f"Product {line.product_id} is not available.")
            if product.stock_qty < line.quantity:
                raise InsufficientStock(f"Not enough stock for {product.name}.")

            line_total = (product.price_npr * line.quantity).quantize(Decimal("0.01"))
            invoice_lines.append(
                InvoiceLineInput(
                    description=product.name,
                    quantity=line.quantity,
                    unit_price_npr=product.price_npr,
                    line_total_npr=line_total,
                )
            )
            subtotal += line_total

        invoice = create_draft_invoice(
            gym, member, invoice_lines, subtotal, Decimal("0.00"), subtotal, actor=actor
        )
        sale = Sale.objects.create(org=gym.org, gym=gym, invoice=invoice, created_by=actor)
        for line, invoice_line in zip(lines, invoice_lines, strict=True):
            product = products[line.product_id]
            SaleLine.objects.create(
                org=gym.org,
                gym=gym,
                sale=sale,
                product=product,
                quantity=line.quantity,
                unit_price_npr=invoice_line.unit_price_npr,
                line_total_npr=invoice_line.line_total_npr,
            )
            product.stock_qty -= line.quantity
            product.save(update_fields=["stock_qty"])

        return sale


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

        # Lazy import: same cross-app-circular-import shape as this module's
        # existing lazy imports of members.services below.
        from publicapi.services import dispatch_webhook_event

        dispatch_webhook_event(
            locked.org,
            "payment.completed",
            {
                "payment_id": locked.pk,
                "member_id": locked.member_id,
                "amount_npr": str(locked.amount_npr),
                "invoice_number": locked.invoice.number if locked.invoice else "",
            },
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
