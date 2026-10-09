"""VAT math (FR-4.x). Pure Python, no Django imports — rule 9.

Nepal VAT is a flat 13%. An org prices items either VAT-inclusive (the
sticker price already contains VAT) or VAT-exclusive (VAT is added on top)
— Organization.vat_inclusive_pricing controls which. Invoice-level totals
sum each line's own already-rounded taxable/vat/total rather than rounding
once on a pre-summed total: that's what makes a multi-line invoice's VAT
line always equal what each line's own receipt would independently show,
and matches the per-value-quantize convention members/domain/renewal.py
and core/domain/money.py already use.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import NamedTuple

VAT_RATE = Decimal("0.13")
TWO_DP = Decimal("0.01")


def _round(amount: Decimal) -> Decimal:
    return amount.quantize(TWO_DP, rounding=ROUND_HALF_UP)


class LineVat(NamedTuple):
    taxable_npr: Decimal
    vat_npr: Decimal
    total_npr: Decimal


def vat_for_line(amount_npr: Decimal, *, inclusive: bool) -> LineVat:
    """amount_npr is the line's price as entered: VAT-inclusive if
    `inclusive`, otherwise VAT-exclusive (VAT is added on top of it).
    """
    if inclusive:
        taxable = _round(amount_npr / (1 + VAT_RATE))
        vat = _round(amount_npr - taxable)
        total = amount_npr
    else:
        taxable = amount_npr
        vat = _round(amount_npr * VAT_RATE)
        total = _round(taxable + vat)
    return LineVat(taxable_npr=taxable, vat_npr=vat, total_npr=total)


class InvoiceVat(NamedTuple):
    taxable_npr: Decimal
    vat_npr: Decimal
    total_npr: Decimal


def vat_for_invoice(line_amounts_npr: list[Decimal], *, inclusive: bool) -> InvoiceVat:
    lines = [vat_for_line(amount, inclusive=inclusive) for amount in line_amounts_npr]
    zero = Decimal("0.00")
    return InvoiceVat(
        taxable_npr=sum((line.taxable_npr for line in lines), zero),
        vat_npr=sum((line.vat_npr for line in lines), zero),
        total_npr=sum((line.total_npr for line in lines), zero),
    )
