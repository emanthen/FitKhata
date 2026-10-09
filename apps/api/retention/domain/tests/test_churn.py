from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from retention.domain.churn import churn_score

# --- fixed-input sanity cases, matching the docstring's documented weights --


def test_a_fresh_active_member_scores_near_zero():
    score = churn_score(
        days_absent=0,
        visits_last_30=12,
        visits_prev_30=12,
        days_to_expiry=200,
        dues_npr=0,
        tenure_days=400,
    )
    assert score == 0.0


def test_a_long_absent_expired_indebted_new_member_scores_near_max():
    score = churn_score(
        days_absent=60,
        visits_last_30=0,
        visits_prev_30=10,
        days_to_expiry=-30,
        dues_npr=500,
        tenure_days=0,
    )
    assert score == 100.0


def test_outstanding_dues_alone_adds_exactly_ten():
    with_dues = churn_score(0, 10, 10, 200, 500, 400)
    without_dues = churn_score(0, 10, 10, 200, 0, 400)
    assert with_dues - without_dues == 10.0


def test_score_is_always_within_bounds():
    score = churn_score(
        days_absent=9999,
        visits_last_30=0,
        visits_prev_30=9999,
        days_to_expiry=-9999,
        dues_npr=9999,
        tenure_days=0,
    )
    assert 0.0 <= score <= 100.0


# --- the one hard requirement: monotonic in days_absent ---------------------


@given(
    days_absent=st.integers(min_value=0, max_value=365),
    extra_days=st.integers(min_value=0, max_value=365),
    visits_last_30=st.integers(min_value=0, max_value=30),
    visits_prev_30=st.integers(min_value=0, max_value=30),
    days_to_expiry=st.integers(min_value=-365, max_value=365),
    dues_npr=st.floats(min_value=0, max_value=1_000_000, allow_nan=False),
    tenure_days=st.integers(min_value=0, max_value=3650),
)
def test_more_absence_never_lowers_the_score(
    days_absent, extra_days, visits_last_30, visits_prev_30, days_to_expiry, dues_npr, tenure_days
):
    lower = churn_score(
        days_absent, visits_last_30, visits_prev_30, days_to_expiry, dues_npr, tenure_days
    )
    higher = churn_score(
        days_absent + extra_days,
        visits_last_30,
        visits_prev_30,
        days_to_expiry,
        dues_npr,
        tenure_days,
    )
    assert higher >= lower
