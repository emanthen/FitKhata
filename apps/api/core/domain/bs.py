"""AD <-> BS (Bikram Sambat) conversion. Pure Python, no Django imports.

Lookup table covers BS 2070-2100 (~AD 2013-04-14 to AD 2044-04-13), sourced
from and cross-checked against two independently maintained open-source BS
calendars (sbmdkl/nepali-date-converter and SuprimKhatri77/go-bs), which
agree on every year in this range except one single-cell typo in the latter
for BS 2087 (discarded in favour of the former, which sums to a valid
365/366-day year). BS 2096 legitimately sums to 364 days in both sources.

Note: Nepal's calendar authority (Nepal Panchang Nirnayak Samiti) only
gazettes a handful of years ahead of the present. Only years up to roughly
the date this table was assembled (BS ~2083, AD 2026) are "official"; later
years in this table are the best unofficial forward projection available
and may be revised once officially published — re-verify before relying on
dates beyond BS ~2085 for anything consequential.
"""

from __future__ import annotations

from datetime import date, timedelta

MIN_BS_YEAR = 2070
MAX_BS_YEAR = 2100

# BS year -> 12 month lengths (Baisakh..Chaitra)
BS_MONTH_LENGTHS: dict[int, tuple[int, ...]] = {
    2070: (31, 31, 31, 32, 31, 31, 29, 30, 30, 29, 30, 30),
    2071: (31, 31, 32, 31, 31, 31, 30, 29, 30, 29, 30, 30),
    2072: (31, 32, 31, 32, 31, 30, 30, 29, 30, 29, 30, 30),
    2073: (31, 32, 31, 32, 31, 30, 30, 30, 29, 29, 30, 31),
    2074: (31, 31, 31, 32, 31, 31, 30, 29, 30, 29, 30, 30),
    2075: (31, 31, 32, 31, 31, 31, 30, 29, 30, 29, 30, 30),
    2076: (31, 32, 31, 32, 31, 30, 30, 30, 29, 29, 30, 30),
    2077: (31, 32, 31, 32, 31, 30, 30, 30, 29, 30, 29, 31),
    2078: (31, 31, 31, 32, 31, 31, 30, 29, 30, 29, 30, 30),
    2079: (31, 31, 32, 31, 31, 31, 30, 29, 30, 29, 30, 30),
    2080: (31, 32, 31, 32, 31, 30, 30, 30, 29, 29, 30, 30),
    2081: (31, 32, 31, 32, 31, 30, 30, 30, 29, 30, 29, 31),
    2082: (31, 31, 32, 31, 31, 31, 30, 29, 30, 29, 30, 30),
    2083: (31, 31, 32, 31, 31, 31, 30, 29, 30, 29, 30, 30),
    2084: (31, 31, 32, 31, 31, 30, 30, 30, 29, 30, 30, 30),
    2085: (31, 32, 31, 32, 30, 31, 30, 30, 29, 30, 30, 30),
    2086: (30, 32, 31, 32, 31, 30, 30, 30, 29, 30, 30, 30),
    2087: (31, 31, 32, 31, 31, 31, 30, 30, 29, 30, 30, 30),
    2088: (30, 31, 32, 32, 30, 31, 30, 30, 29, 30, 30, 30),
    2089: (30, 32, 31, 32, 31, 30, 30, 30, 29, 30, 30, 30),
    2090: (30, 32, 31, 32, 31, 30, 30, 30, 29, 30, 30, 30),
    2091: (31, 31, 32, 31, 31, 31, 30, 30, 29, 30, 30, 30),
    2092: (30, 31, 32, 32, 31, 30, 30, 30, 29, 30, 30, 30),
    2093: (30, 32, 31, 32, 31, 30, 30, 30, 29, 30, 30, 30),
    2094: (31, 31, 32, 31, 31, 30, 30, 30, 29, 30, 30, 30),
    2095: (31, 31, 32, 31, 31, 31, 30, 29, 30, 30, 30, 30),
    2096: (30, 31, 32, 32, 31, 30, 30, 29, 30, 29, 30, 30),
    2097: (31, 32, 31, 32, 31, 30, 30, 30, 29, 30, 30, 30),
    2098: (31, 31, 32, 31, 31, 31, 29, 30, 29, 30, 29, 31),
    2099: (31, 32, 31, 32, 31, 30, 30, 30, 29, 29, 30, 31),
    2100: (31, 32, 31, 32, 31, 30, 30, 30, 29, 29, 30, 31),
}

# BS 2070-01-01 == AD 2013-04-14 (Nepali New Year), the anchor for this table.
_ANCHOR_BS_YEAR = 2070
_ANCHOR_AD = date(2013, 4, 14)

MONTH_NAMES_EN = (
    "Baisakh", "Jestha", "Ashadh", "Shrawan", "Bhadra", "Ashwin",
    "Kartik", "Mangsir", "Poush", "Magh", "Falgun", "Chaitra",
)
MONTH_NAMES_NE = (
    "बैशाख", "जेठ", "असार", "श्रावण", "भदौ", "असोज",
    "कार्तिक", "मंसिर", "पुष", "माघ", "फागुन", "चैत",
)
_NE_DIGITS = str.maketrans("0123456789", "०१२३४५६७८९")


def _year_length(year: int) -> int:
    return sum(BS_MONTH_LENGTHS[year])


def to_bs(ad_date: date) -> tuple[int, int, int]:
    """Convert an AD date to (BS year, BS month 1-12, BS day) within the table's range."""
    offset = (ad_date - _ANCHOR_AD).days
    if offset < 0:
        raise ValueError(f"{ad_date} is before the BS lookup table starts ({_ANCHOR_AD})")

    year = _ANCHOR_BS_YEAR
    while offset >= _year_length(year):
        offset -= _year_length(year)
        year += 1
        if year > MAX_BS_YEAR:
            raise ValueError(f"{ad_date} is beyond the BS lookup table (max BS {MAX_BS_YEAR})")

    month_lengths = BS_MONTH_LENGTHS[year]
    month = 1
    for length in month_lengths:
        if offset < length:
            break
        offset -= length
        month += 1

    return year, month, offset + 1


def to_ad(bs_year: int, bs_month: int, bs_day: int) -> date:
    """Convert a BS (year, month, day) within the table's range to an AD date."""
    if not (MIN_BS_YEAR <= bs_year <= MAX_BS_YEAR):
        raise ValueError(
            f"BS year {bs_year} is outside the lookup table ({MIN_BS_YEAR}-{MAX_BS_YEAR})"
        )
    if not (1 <= bs_month <= 12):
        raise ValueError(f"BS month {bs_month} out of range")
    month_lengths = BS_MONTH_LENGTHS[bs_year]
    if not (1 <= bs_day <= month_lengths[bs_month - 1]):
        raise ValueError(f"BS day {bs_day} out of range for {bs_year}-{bs_month:02d}")

    days = 0
    for year in range(_ANCHOR_BS_YEAR, bs_year):
        days += _year_length(year)
    days += sum(month_lengths[: bs_month - 1])
    days += bs_day - 1
    return _ANCHOR_AD + timedelta(days=days)


def format_bs(ad_date: date, lang: str = "en") -> str:
    """Format an AD date as a BS date string, e.g. '2083 Shrawan 17' or '२०८३ श्रावण १७'."""
    year, month, day = to_bs(ad_date)
    if lang == "ne":
        month_name = MONTH_NAMES_NE[month - 1]
        return f"{year} {month_name} {day}".translate(_NE_DIGITS)
    month_name = MONTH_NAMES_EN[month - 1]
    return f"{year} {month_name} {day}"


def month_range(bs_year: int, bs_month: int) -> tuple[date, date]:
    """The AD (start, end) dates spanned by one BS month — e.g. for
    payroll.services turning a PayrollRun.period_bs 'YYYY-MM' into the AD
    date range its shifts/attendance/advances/commissions fall in.
    """
    start = to_ad(bs_year, bs_month, 1)
    last_day = BS_MONTH_LENGTHS[bs_year][bs_month - 1]
    end = to_ad(bs_year, bs_month, last_day)
    return start, end
