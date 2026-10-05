from decimal import Decimal

import pytest

from core.domain.money import format_npr


@pytest.mark.parametrize(
    ("amount", "expected"),
    [
        (Decimal("0"), "0.00"),
        (Decimal("5"), "5.00"),
        (Decimal("50"), "50.00"),
        (Decimal("500"), "500.00"),
        (Decimal("5000"), "5,000.00"),
        (Decimal("50000"), "50,000.00"),
        (Decimal("100000"), "1,00,000.00"),
        (Decimal("1234567"), "12,34,567.00"),
        (Decimal("1234567.5"), "12,34,567.50"),
        (Decimal("12345678"), "1,23,45,678.00"),
        (Decimal("999"), "999.00"),
        (Decimal("1000"), "1,000.00"),
        (Decimal("1234567.5"), "12,34,567.50"),
    ],
)
def test_format_npr_grouping(amount: Decimal, expected: str) -> None:
    assert format_npr(amount) == expected


def test_format_npr_negative() -> None:
    assert format_npr(Decimal("-1234567.5")) == "-12,34,567.50"


def test_format_npr_rounds_half_up() -> None:
    assert format_npr(Decimal("10.005")) == "10.01"
    assert format_npr(Decimal("10.004")) == "10.00"
    assert format_npr(Decimal("10.015")) == "10.02"


def test_format_npr_pads_single_decimal() -> None:
    assert format_npr(Decimal("10.1")) == "10.10"


def test_format_npr_with_symbol() -> None:
    assert format_npr(Decimal("1234567.5"), symbol=True) == "Rs. 12,34,567.50"


def test_format_npr_small_group_no_commas() -> None:
    assert format_npr(Decimal("99.99")) == "99.99"
