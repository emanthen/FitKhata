from datetime import UTC, date, datetime

import pytest

from core.domain.nptime import KATHMANDU, fiscal_year, start_of_day_npt, to_kathmandu


def test_to_kathmandu_offset_is_5_45() -> None:
    utc_dt = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    npt_dt = to_kathmandu(utc_dt)
    offset = npt_dt.utcoffset()
    assert offset is not None
    assert offset.total_seconds() == 5 * 3600 + 45 * 60


def test_to_kathmandu_rejects_naive() -> None:
    with pytest.raises(ValueError):
        to_kathmandu(datetime(2026, 1, 1))


def test_to_kathmandu_crosses_midnight() -> None:
    # 19:30 UTC -> 01:15 next day in Kathmandu (+05:45)
    utc_dt = datetime(2026, 1, 1, 19, 30, tzinfo=UTC)
    npt_dt = to_kathmandu(utc_dt)
    assert (npt_dt.date(), npt_dt.hour, npt_dt.minute) == (date(2026, 1, 2), 1, 15)


def test_start_of_day_npt_is_midnight_local() -> None:
    utc_dt = datetime(2026, 1, 1, 19, 30, tzinfo=UTC)
    start = start_of_day_npt(utc_dt)
    assert (start.hour, start.minute, start.second) == (0, 0, 0)
    assert start.tzinfo is not None
    assert start.date() == date(2026, 1, 2)


def test_start_of_day_npt_same_calendar_day() -> None:
    utc_dt = datetime(2026, 1, 1, 3, 0, tzinfo=UTC)  # 08:45 NPT
    start = start_of_day_npt(utc_dt)
    assert start.date() == date(2026, 1, 1)


@pytest.mark.parametrize(
    ("d", "fy"),
    [
        (date(2026, 8, 15), "2083/84"),
        (date(2026, 6, 15), "2082/83"),
        (date(2026, 7, 17), "2083/84"),  # Shrawan 1, 2083 - exact boundary start
        (date(2026, 7, 16), "2082/83"),  # day before the boundary
        (date(2025, 4, 14), "2081/82"),  # Baisakh 1, 2082 - still FY 2081/82
        (date(2027, 7, 17), "2084/85"),
    ],
)
def test_fiscal_year(d: date, fy: str) -> None:
    assert fiscal_year(d) == fy


def test_kathmandu_zone_name() -> None:
    assert str(KATHMANDU) == "Asia/Kathmandu"
