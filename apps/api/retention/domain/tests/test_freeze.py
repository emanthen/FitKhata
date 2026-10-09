from __future__ import annotations

from datetime import date, timedelta

from hypothesis import given
from hypothesis import strategies as st

from retention.domain.freeze import apply_freeze, revert_freeze


def test_a_single_day_freeze_adds_exactly_one_day():
    new_expiry, days = apply_freeze(date(2026, 1, 31), date(2026, 10, 5), date(2026, 10, 5))
    assert days == 1
    assert new_expiry == date(2026, 2, 1)


def test_a_ten_day_dashain_freeze_adds_ten_days():
    new_expiry, days = apply_freeze(date(2026, 1, 31), date(2026, 10, 1), date(2026, 10, 10))
    assert days == 10
    assert new_expiry == date(2026, 2, 10)


def test_revert_restores_the_exact_previous_expiry():
    expiry = date(2026, 1, 31)
    new_expiry, days = apply_freeze(expiry, date(2026, 10, 1), date(2026, 10, 10))
    assert revert_freeze(new_expiry, days) == expiry


@given(
    expiry=st.dates(min_value=date(2020, 1, 1), max_value=date(2040, 1, 1)),
    start_offset=st.integers(min_value=0, max_value=3650),
    span_days=st.integers(min_value=0, max_value=365),
)
def test_apply_then_revert_is_always_exact(expiry, start_offset, span_days):
    start = date(2020, 1, 1) + timedelta(days=start_offset)
    end = start + timedelta(days=span_days)
    new_expiry, days = apply_freeze(expiry, start, end)
    assert revert_freeze(new_expiry, days) == expiry
