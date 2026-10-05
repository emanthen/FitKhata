from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st

from members.domain.renewal import apply_promo, expiry_for, next_start, prorata_credit


@dataclass
class _Promo:
    kind: str
    value: Decimal


# --- next_start / expiry_for -------------------------------------------


def test_next_start_fresh_membership_starts_today():
    assert next_start(date(2026, 1, 1), None) == date(2026, 1, 1)


def test_next_start_early_renewal_abuts_current_expiry():
    # Renewing 10 days before expiry still starts the day after expiry —
    # the member doesn't lose those 10 remaining days.
    assert next_start(date(2026, 1, 20), date(2026, 1, 30)) == date(2026, 1, 31)


def test_next_start_lapsed_renewal_starts_today():
    assert next_start(date(2026, 2, 15), date(2026, 1, 30)) == date(2026, 2, 15)


def test_expiry_for_is_inclusive_of_start_day():
    # A 30-day plan starting Jan 1 covers 30 calendar days: Jan 1..Jan 30.
    assert expiry_for(date(2026, 1, 1), 30) == date(2026, 1, 30)


@given(
    first_start=st.dates(min_value=date(2000, 1, 1), max_value=date(2090, 1, 1)),
    plan=st.lists(
        st.tuples(
            st.integers(min_value=1, max_value=400),  # duration_days
            st.integers(min_value=0, max_value=400),  # days-before-expiry renewed
        ),
        min_size=1,
        max_size=15,
    ),
)
def test_early_renewal_chain_never_loses_or_duplicates_a_day(first_start, plan):
    """FR-2.5 property: as long as every renewal happens on or before the
    current expiry, the total covered span equals exactly the sum of every
    period's duration — no gap, no overlap, regardless of how early.
    """
    start = next_start(first_start, None)
    expiry = expiry_for(start, plan[0][0])
    total_duration = plan[0][0]

    for duration_days, early_by in plan[1:]:
        today = expiry - timedelta(days=min(early_by, (expiry - start).days))
        start_i = next_start(today, expiry)
        assert start_i == expiry + timedelta(days=1)  # the actual "no days lost" claim
        expiry = expiry_for(start_i, duration_days)
        total_duration += duration_days

    span_days = (expiry - start).days + 1
    assert span_days == total_duration


# --- apply_promo ----------------------------------------------------------


def test_apply_promo_none_returns_price_unchanged():
    assert apply_promo(Decimal("1000.00"), None) == Decimal("1000.00")


def test_apply_promo_flat():
    assert apply_promo(Decimal("1000.00"), _Promo("flat", Decimal("150"))) == Decimal("850.00")


def test_apply_promo_percent():
    assert apply_promo(Decimal("1000.00"), _Promo("percent", Decimal("10"))) == Decimal("900.00")


def test_apply_promo_flat_never_goes_negative():
    assert apply_promo(Decimal("100.00"), _Promo("flat", Decimal("500"))) == Decimal("0.00")


def test_apply_promo_rounds_to_two_decimal_places():
    assert apply_promo(Decimal("100.00"), _Promo("percent", Decimal("33"))) == Decimal("67.00")


# --- prorata_credit ---------------------------------------------------------


def test_prorata_credit_full_remaining_period():
    # 30-day plan at 3000, upgrading on the very first day: all 30 days remain.
    credit = prorata_credit(date(2026, 1, 30), Decimal("3000.00"), 30, date(2026, 1, 1))
    assert credit == Decimal("3000.00")


def test_prorata_credit_no_remaining_days_is_zero():
    credit = prorata_credit(date(2026, 1, 30), Decimal("3000.00"), 30, date(2026, 2, 15))
    assert credit == Decimal("0.00")


def test_prorata_credit_partial():
    # 10 days remain (today counts as used) out of a 30-day, 3000 plan.
    credit = prorata_credit(date(2026, 1, 30), Decimal("3000.00"), 30, date(2026, 1, 21))
    assert credit == Decimal("1000.00")
