from __future__ import annotations

from datetime import datetime

from members.domain.access import is_within_access_hours


def test_empty_dict_is_unrestricted():
    monday_3am = datetime(2026, 10, 5, 3, 0)  # Oct 5 2026 is a Monday
    assert is_within_access_hours({}, monday_3am) is True


def test_explicit_always_is_unrestricted():
    assert is_within_access_hours({"always": True}, datetime(2026, 10, 5, 3, 0)) is True


def test_within_a_window():
    windows = {"windows": [{"day": "mon", "start": "06:00", "end": "22:00"}]}
    assert is_within_access_hours(windows, datetime(2026, 10, 5, 12, 0)) is True


def test_outside_a_window_same_day():
    windows = {"windows": [{"day": "mon", "start": "06:00", "end": "22:00"}]}
    assert is_within_access_hours(windows, datetime(2026, 10, 5, 23, 0)) is False


def test_wrong_day_is_rejected():
    windows = {"windows": [{"day": "mon", "start": "06:00", "end": "22:00"}]}
    tuesday_noon = datetime(2026, 10, 6, 12, 0)
    assert is_within_access_hours(windows, tuesday_noon) is False


def test_window_boundaries_are_inclusive():
    windows = {"windows": [{"day": "mon", "start": "06:00", "end": "22:00"}]}
    assert is_within_access_hours(windows, datetime(2026, 10, 5, 6, 0)) is True
    assert is_within_access_hours(windows, datetime(2026, 10, 5, 22, 0)) is True


def test_multiple_windows_same_day():
    windows = {
        "windows": [
            {"day": "mon", "start": "05:00", "end": "09:00"},
            {"day": "mon", "start": "17:00", "end": "21:00"},
        ]
    }
    assert is_within_access_hours(windows, datetime(2026, 10, 5, 7, 0)) is True
    assert is_within_access_hours(windows, datetime(2026, 10, 5, 12, 0)) is False
    assert is_within_access_hours(windows, datetime(2026, 10, 5, 18, 0)) is True
