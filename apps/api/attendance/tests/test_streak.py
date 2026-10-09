from __future__ import annotations

from datetime import date, timedelta

from attendance.domain.streak import compute_streaks

TODAY = date.today()


def test_empty() -> None:
    assert compute_streaks([]) == (0, 0)


def test_single_day_today() -> None:
    assert compute_streaks([TODAY]) == (1, 1)


def test_consecutive_run_ending_today() -> None:
    days = [TODAY - timedelta(days=i) for i in range(5)]
    assert compute_streaks(days) == (5, 5)


def test_gap_breaks_current_but_not_longest() -> None:
    days = [
        TODAY,
        TODAY - timedelta(days=1),
        TODAY - timedelta(days=5),
        TODAY - timedelta(days=6),
        TODAY - timedelta(days=7),
    ]
    current, longest = compute_streaks(days)
    assert current == 2
    assert longest == 3


def test_lapsed_streak_has_zero_current() -> None:
    days = [TODAY - timedelta(days=3), TODAY - timedelta(days=4), TODAY - timedelta(days=5)]
    current, longest = compute_streaks(days)
    assert current == 0
    assert longest == 3


def test_most_recent_yesterday_counts_as_current() -> None:
    days = [TODAY - timedelta(days=1), TODAY - timedelta(days=2)]
    current, longest = compute_streaks(days)
    assert current == 2
    assert longest == 2
