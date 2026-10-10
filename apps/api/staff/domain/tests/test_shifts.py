from datetime import date, time

from staff.domain.shifts import overlaps

DAY = date(2026, 10, 10)
OTHER_DAY = date(2026, 10, 11)


def test_identical_times_overlap() -> None:
    a = (DAY, time(9, 0), time(17, 0))
    b = (DAY, time(9, 0), time(17, 0))
    assert overlaps(a, b) is True


def test_nested_shift_overlaps() -> None:
    a = (DAY, time(9, 0), time(17, 0))
    b = (DAY, time(11, 0), time(13, 0))
    assert overlaps(a, b) is True


def test_touching_not_overlapping_is_not_a_conflict() -> None:
    a = (DAY, time(9, 0), time(13, 0))
    b = (DAY, time(13, 0), time(17, 0))
    assert overlaps(a, b) is False
    assert overlaps(b, a) is False


def test_disjoint_shifts_do_not_overlap() -> None:
    a = (DAY, time(9, 0), time(11, 0))
    b = (DAY, time(14, 0), time(17, 0))
    assert overlaps(a, b) is False


def test_different_dates_never_overlap_even_with_identical_times() -> None:
    a = (DAY, time(9, 0), time(17, 0))
    b = (OTHER_DAY, time(9, 0), time(17, 0))
    assert overlaps(a, b) is False
