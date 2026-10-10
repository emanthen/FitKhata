"""VAT sales register row shaping (FR-10.7), IRD column order. Pure Python,
no Django imports — rule 9. Takes already-fetched invoice-like objects (any
object with these attributes) so this stays testable without a DB.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from decimal import Decimal
from typing import Any

ZERO = Decimal("0.00")


def vat_register_rows(invoices: Iterable[Any]) -> list[dict[str, Any]]:
    """One row per invoice, IRD sales-register column order."""
    return [
        {
            "bill_date_bs": inv.bill_date_bs,
            "number": inv.number,
            "buyer_name": inv.buyer_name,
            "buyer_pan": inv.buyer_pan,
            "taxable_npr": inv.taxable_npr,
            "vat_npr": inv.vat_npr,
            "total_npr": inv.total_npr,
        }
        for inv in invoices
    ]


def vat_register_monthly_totals(invoices: Iterable[Any]) -> dict[str, dict[str, Decimal]]:
    """Keyed by BS "YYYY-MM" (bill_date_bs's own first 7 characters — it's
    already a stored BS string, no AD conversion needed).
    """
    totals: dict[str, dict[str, Decimal]] = defaultdict(
        lambda: {"taxable_npr": ZERO, "vat_npr": ZERO, "total_npr": ZERO}
    )
    for inv in invoices:
        month = inv.bill_date_bs[:7]
        totals[month]["taxable_npr"] += inv.taxable_npr
        totals[month]["vat_npr"] += inv.vat_npr
        totals[month]["total_npr"] += inv.total_npr
    return dict(totals)
