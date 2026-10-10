from datetime import UTC, datetime, time

from staff.domain.attendance import is_late


def _clock_in(hour: int, minute: int, second: int = 0) -> datetime:
    return datetime(2026, 10, 10, hour, minute, second, tzinfo=UTC)


def test_exactly_at_grace_boundary_is_not_late() -> None:
    assert is_late(_clock_in(9, 10, 0), time(9, 0), grace_minutes=10) is False


def test_one_second_past_grace_boundary_is_late() -> None:
    assert is_late(_clock_in(9, 10, 1), time(9, 0), grace_minutes=10) is True


def test_one_second_before_grace_boundary_is_not_late() -> None:
    assert is_late(_clock_in(9, 9, 59), time(9, 0), grace_minutes=10) is False


def test_well_within_grace_is_not_late() -> None:
    assert is_late(_clock_in(9, 2), time(9, 0), grace_minutes=10) is False


def test_well_past_grace_is_late() -> None:
    assert is_late(_clock_in(9, 45), time(9, 0), grace_minutes=10) is True


def test_zero_grace_boundary_is_not_late() -> None:
    assert is_late(_clock_in(9, 0, 0), time(9, 0), grace_minutes=0) is False
