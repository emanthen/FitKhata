"""Cash-drawer math (FR-4.10). Pure Python, no Django imports — rule 9."""

from __future__ import annotations

from decimal import Decimal


def expected_cash(
    opening_float_npr: Decimal,
    cash_payments_npr: Decimal,
    cash_refunds_npr: Decimal = Decimal("0"),
) -> Decimal:
    """Drawer expected = opening float + cash payments − cash refunds."""
    return opening_float_npr + cash_payments_npr - cash_refunds_npr


def variance(expected_npr: Decimal, counted_npr: Decimal) -> Decimal:
    return counted_npr - expected_npr
