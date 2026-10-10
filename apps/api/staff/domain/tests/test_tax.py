from decimal import Decimal
from typing import Any

import pytest

from staff.domain.tax import SlabFileError, compute_tds, load_slabs

# A fixed, inline slab table for pure-math boundary testing — deliberately
# NOT the shipped staff/tax/slabs_2083_84.yaml file (that one is flagged
# as an unverified placeholder; these numbers exist only to exercise the
# cumulative-bracket math, not to assert real tax law).
SLABS: list[dict[str, Any]] = [
    {"upto": 500000, "rate_pct": 1},
    {"upto": 700000, "rate_pct": 10},
    {"upto": 1000000, "rate_pct": 20},
    {"upto": 2000000, "rate_pct": 30},
    {"upto": None, "rate_pct": 36},
]


def test_zero_income_is_zero_tax() -> None:
    assert compute_tds(Decimal("0"), SLABS) == Decimal("0.00")


def test_negative_income_rejected() -> None:
    with pytest.raises(ValueError):
        compute_tds(Decimal("-1"), SLABS)


@pytest.mark.parametrize(
    ("income", "expected"),
    [
        (Decimal("499999"), Decimal("4999.99")),  # just below slab 1 boundary
        (Decimal("500000"), Decimal("5000.00")),  # exactly at slab 1 boundary
        (Decimal("500001"), Decimal("5000.10")),  # just above slab 1 boundary
        (Decimal("699999"), Decimal("24999.90")),  # just below slab 2 boundary
        (Decimal("700000"), Decimal("25000.00")),  # exactly at slab 2 boundary
        (Decimal("700001"), Decimal("25000.20")),  # just above slab 2 boundary
    ],
)
def test_slab_boundaries(income: Decimal, expected: Decimal) -> None:
    assert compute_tds(income, SLABS) == expected


def test_uncapped_top_band_applies_beyond_the_last_finite_boundary() -> None:
    # 5000 (slab1) + 20000 (slab2) + 60000 (slab3) + 300000 (slab4) + 360000 (slab5)
    assert compute_tds(Decimal("3000000"), SLABS) == Decimal("745000.00")


def test_load_slabs_missing_fiscal_year_raises() -> None:
    with pytest.raises(SlabFileError):
        load_slabs("1900/01")


def test_load_slabs_shipped_file_has_the_expected_shape() -> None:
    """Shape only — this does not assert the shipped figures are correct
    real-world tax law. See the file's own `confirmed: false` flag.
    """
    data = load_slabs("2083/84")
    assert data["fiscal_year"] == "2083/84"
    assert isinstance(data["confirmed"], bool)
    assert data["slabs"][-1]["upto"] is None
