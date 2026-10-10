from datetime import date

import pytest

from core.domain.bs import format_bs, month_range, to_ad, to_bs


def test_bs_new_year_anchor() -> None:
    assert to_bs(date(2013, 4, 14)) == (2070, 1, 1)


@pytest.mark.parametrize(
    ("ad", "bs"),
    [
        (date(2013, 4, 14), (2070, 1, 1)),
        (date(2023, 4, 14), (2080, 1, 1)),
        (date(2025, 4, 14), (2082, 1, 1)),
        (date(2026, 4, 14), (2083, 1, 1)),
        (date(2026, 7, 17), (2083, 4, 1)),
        (date(2026, 7, 16), (2083, 3, 32)),  # Ashadh 2083 has 32 days
        (date(2026, 8, 15), (2083, 4, 30)),
        (date(2026, 10, 1), (2083, 6, 15)),
    ],
)
def test_to_bs_known_dates(ad: date, bs: tuple[int, int, int]) -> None:
    assert to_bs(ad) == bs


@pytest.mark.parametrize(
    ("bs", "ad"),
    [
        ((2070, 1, 1), date(2013, 4, 14)),
        ((2083, 1, 1), date(2026, 4, 14)),
        ((2083, 4, 1), date(2026, 7, 17)),
    ],
)
def test_to_ad_known_dates(bs: tuple[int, int, int], ad: date) -> None:
    assert to_ad(*bs) == ad


@pytest.mark.parametrize(
    "ad",
    [date(2013, 4, 14), date(2026, 10, 1), date(2030, 1, 1), date(2040, 12, 31)],
)
def test_to_bs_to_ad_round_trip(ad: date) -> None:
    y, m, d = to_bs(ad)
    assert to_ad(y, m, d) == ad


def test_to_bs_before_table_raises() -> None:
    with pytest.raises(ValueError):
        to_bs(date(2013, 4, 13))


def test_to_ad_invalid_month_raises() -> None:
    with pytest.raises(ValueError):
        to_ad(2083, 13, 1)


def test_to_ad_invalid_day_raises() -> None:
    with pytest.raises(ValueError):
        to_ad(2083, 1, 32)


def test_format_bs_english() -> None:
    assert format_bs(date(2026, 7, 17)) == "2083 Shrawan 1"


def test_format_bs_nepali() -> None:
    assert format_bs(date(2026, 7, 17), lang="ne") == "२०८३ श्रावण १"


# BS new year falls mid-April, so every BS month straddles two AD months —
# there's no "doesn't cross" case to test against this calendar.
@pytest.mark.parametrize(
    ("bs_year", "bs_month", "start", "end"),
    [
        (2083, 4, date(2026, 7, 17), date(2026, 8, 16)),  # 31-day Shrawan
        (2083, 8, date(2026, 11, 17), date(2026, 12, 15)),  # 29-day Mangsir
    ],
)
def test_month_range(bs_year: int, bs_month: int, start: date, end: date) -> None:
    assert month_range(bs_year, bs_month) == (start, end)


def test_month_range_round_trips_through_to_bs() -> None:
    from core.domain.bs import BS_MONTH_LENGTHS

    start, end = month_range(2083, 6)
    assert to_bs(start) == (2083, 6, 1)
    assert to_bs(end) == (2083, 6, BS_MONTH_LENGTHS[2083][5])
