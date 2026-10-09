from __future__ import annotations

from decimal import Decimal

from billing.domain.shift import expected_cash, variance


def test_expected_cash_is_float_plus_payments():
    result = expected_cash(Decimal("5000.00"), Decimal("12500.00"))
    assert result == Decimal("17500.00")


def test_expected_cash_subtracts_refunds():
    result = expected_cash(Decimal("5000.00"), Decimal("12500.00"), Decimal("1000.00"))
    assert result == Decimal("16500.00")


def test_variance_positive_when_counted_exceeds_expected():
    assert variance(Decimal("17500.00"), Decimal("17650.00")) == Decimal("150.00")


def test_variance_negative_when_counted_is_short():
    assert variance(Decimal("17500.00"), Decimal("17350.00")) == Decimal("-150.00")


def test_variance_zero_when_drawer_balances():
    assert variance(Decimal("17500.00"), Decimal("17500.00")) == Decimal("0.00")
