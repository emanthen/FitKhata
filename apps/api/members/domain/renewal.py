"""Pure membership-period math (FR-2.5/2.6). No Django imports — rule 9.

Convention: `duration_days` is inclusive of the start day. A 30-day plan
starting 2026-01-01 runs through 2026-01-30 (30 calendar days total), so
`expiry_for` is `start + (duration_days - 1)`. That convention is what
makes `next_start`'s "current_expiry + 1 day" abut the previous period
exactly — no gap day, no overlap day — which is the property the
early-renewal hypothesis test checks.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Protocol

TWO_DP = Decimal("0.01")


def next_start(today: date, current_expiry: date | None) -> date:
    """The start date for a new/renewed membership period."""
    if current_expiry is None:
        return today
    return max(today, current_expiry + timedelta(days=1))


def expiry_for(start: date, duration_days: int) -> date:
    return start + timedelta(days=duration_days - 1)


class Promo(Protocol):
    kind: str  # "flat" | "percent"
    value: Decimal


def apply_promo(price: Decimal, promo: Promo | None) -> Decimal:
    """Price after a promo code — never negative, rounded to 2dp."""
    if promo is None:
        return price.quantize(TWO_DP, rounding=ROUND_HALF_UP)
    if promo.kind == "flat":
        result = price - promo.value
    elif promo.kind == "percent":
        result = price * (Decimal(100) - promo.value) / Decimal(100)
    else:
        raise ValueError(f"Unknown promo kind: {promo.kind!r}")
    return max(Decimal("0"), result).quantize(TWO_DP, rounding=ROUND_HALF_UP)


def prorata_credit(
    old_expiry: date,
    old_price: Decimal,
    old_duration_days: int,
    today: date,
) -> Decimal:
    """Credit for the unused remainder of a membership being upgraded
    mid-cycle (FR-2.6). This implementation's own interpretation — no SRS
    formula available (same situation as accounts/permissions.py in
    Phase 1): daily_rate * remaining whole days (today counts as used).
    """
    daily_rate = old_price / Decimal(old_duration_days)
    remaining_days = max(0, (old_expiry - today).days + 1)
    credit = daily_rate * remaining_days
    return credit.quantize(TWO_DP, rounding=ROUND_HALF_UP)
