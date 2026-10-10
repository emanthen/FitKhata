"""Nepal salary TDS slab engine. Pure Python, no Django imports — rule 9.

Slabs are a versioned YAML config per fiscal year (staff/tax/slabs_*.yaml),
because the bands change every Nepali fiscal year and an owner must review
them before they govern real payroll — see load_slabs()'s docstring and
staff.services.finalize_payroll_run's confirmed-flag check (that's the
actual enforcement; this module only validates *shape*, never asserts the
numbers are correct).
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml

ZERO = Decimal("0.00")
TAX_DIR = Path(__file__).resolve().parent.parent / "tax"


class SlabFileError(ValueError):
    pass


def fy_filename(fiscal_year: str) -> str:
    # "2083/84" -> "slabs_2083_84.yaml"
    return f"slabs_{fiscal_year.replace('/', '_')}.yaml"


def load_slabs(fiscal_year: str) -> dict[str, Any]:
    """Loads and shape-validates staff/tax/slabs_<fy>.yaml. Does NOT check
    `confirmed` — that's a business-rule gate services.py enforces at
    finalize, not a loading concern. Raises SlabFileError if the file is
    missing or malformed (missing keys, non-ascending bands, more than
    one unbounded band, etc.) rather than silently computing against junk.
    """
    path = TAX_DIR / fy_filename(fiscal_year)
    if not path.exists():
        raise SlabFileError(f"No tax slab file for fiscal year {fiscal_year!r} at {path}")

    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    for key in ("fiscal_year", "confirmed", "slabs"):
        if key not in data:
            raise SlabFileError(f"Slab file {path} missing required key {key!r}")

    slabs = data["slabs"]
    if not slabs:
        raise SlabFileError(f"Slab file {path} has no slabs")

    previous_upto: float | None = None
    for i, band in enumerate(slabs):
        if "upto" not in band or "rate_pct" not in band:
            raise SlabFileError(f"Slab file {path} band {i} missing 'upto' or 'rate_pct'")
        upto = band["upto"]
        if upto is None and i != len(slabs) - 1:
            raise SlabFileError(f"Slab file {path}: only the last band may be unbounded")
        if upto is not None:
            if previous_upto is not None and upto <= previous_upto:
                raise SlabFileError(f"Slab file {path}: band {i} 'upto' must increase")
            previous_upto = upto

    return data


def compute_tds(annual_taxable_npr: Decimal, slabs: list[dict[str, Any]]) -> Decimal:
    """Standard cumulative marginal-bracket calculation — each band's rate
    applies only to the slice of income within that band, not the whole
    amount. The task's "1% social security tax first slab" rule needs no
    special-casing: it's just the first band's own rate_pct, already
    generic in the data.
    """
    if annual_taxable_npr < 0:
        raise ValueError("annual_taxable_npr must not be negative")

    tax = ZERO
    lower = Decimal("0")
    for band in slabs:
        if annual_taxable_npr <= lower:
            break
        rate = Decimal(str(band["rate_pct"])) / Decimal("100")
        upto = band["upto"]
        upper = Decimal(str(upto)) if upto is not None else annual_taxable_npr
        band_amount = min(annual_taxable_npr, upper) - lower
        if band_amount > 0:
            tax += band_amount * rate
        lower = upper
        if upto is None:
            break
    return tax.quantize(Decimal("0.01"))
