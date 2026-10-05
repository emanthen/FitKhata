"""Draft-invoice creation only — rule 9. Payment confirmation/idempotency
(rules 6/7) is Phase 4; nothing here ever marks an invoice paid or issued.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from django.db import transaction

from billing.models import Invoice, InvoiceCounter, InvoiceLine
from core.domain.bs import to_bs
from core.services import audit

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

        invoice = Invoice.objects.create(
            org=gym.org,
            gym=gym,
            number=number,
            fiscal_year=fiscal_year,
            member=member,
            subtotal_npr=subtotal_npr,
            discount_npr=discount_npr,
            total_npr=total_npr,
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
