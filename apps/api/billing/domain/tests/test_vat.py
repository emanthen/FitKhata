from __future__ import annotations

from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st

from billing.domain.vat import vat_for_invoice, vat_for_line

# --- vat_for_line: exclusive --------------------------------------------


def test_exclusive_adds_13_percent_on_top():
    result = vat_for_line(Decimal("1000.00"), inclusive=False)
    assert result.taxable_npr == Decimal("1000.00")
    assert result.vat_npr == Decimal("130.00")
    assert result.total_npr == Decimal("1130.00")


def test_exclusive_rounds_half_up():
    # 333.33 * 13% = 43.3329 -> rounds to 43.33
    result = vat_for_line(Decimal("333.33"), inclusive=False)
    assert result.vat_npr == Decimal("43.33")
    assert result.total_npr == Decimal("376.66")


# --- vat_for_line: inclusive ----------------------------------------------


def test_inclusive_splits_an_exact_multiple_cleanly():
    # 113.00 is exactly 100.00 taxable + 13.00 VAT.
    result = vat_for_line(Decimal("113.00"), inclusive=True)
    assert result.taxable_npr == Decimal("100.00")
    assert result.vat_npr == Decimal("13.00")
    assert result.total_npr == Decimal("113.00")


def test_inclusive_rounds_the_taxable_portion():
    # 1000 / 1.13 = 884.9557... -> 884.96; VAT is whatever's left, not a
    # second independent rounding, so taxable + vat always reconstructs
    # the original inclusive total exactly.
    result = vat_for_line(Decimal("1000.00"), inclusive=True)
    assert result.taxable_npr == Decimal("884.96")
    assert result.vat_npr == Decimal("115.04")
    assert result.total_npr == Decimal("1000.00")


# --- vat_for_invoice: sums already-rounded lines --------------------------


def test_invoice_sums_per_line_rounded_values():
    result = vat_for_invoice([Decimal("1000.00"), Decimal("500.00")], inclusive=False)
    assert result.taxable_npr == Decimal("1500.00")
    assert result.vat_npr == Decimal("195.00")
    assert result.total_npr == Decimal("1695.00")


def test_invoice_matches_sum_of_independently_computed_lines():
    amounts = [Decimal("333.33"), Decimal("666.66"), Decimal("111.11")]
    invoice_result = vat_for_invoice(amounts, inclusive=False)
    line_results = [vat_for_line(a, inclusive=False) for a in amounts]
    assert invoice_result.vat_npr == sum((r.vat_npr for r in line_results), Decimal("0.00"))
    assert invoice_result.total_npr == sum((r.total_npr for r in line_results), Decimal("0.00"))


# --- property: taxable + vat always reconstructs the total ----------------


@given(
    amount=st.decimals(
        min_value=Decimal("0.01"), max_value=Decimal("10000000.00"), places=2
    ),
    inclusive=st.booleans(),
)
def test_taxable_plus_vat_always_equals_total(amount, inclusive):
    result = vat_for_line(amount, inclusive=inclusive)
    assert result.taxable_npr + result.vat_npr == result.total_npr
