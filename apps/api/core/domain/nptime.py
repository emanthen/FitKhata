"""Nepal time helpers. Pure Python, no Django imports — see CLAUDE.md rule 5."""

from __future__ import annotations

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from .bs import to_bs

KATHMANDU = ZoneInfo("Asia/Kathmandu")  # UTC+05:45


def to_kathmandu(dt: datetime) -> datetime:
    """Convert an aware datetime (any tz, typically UTC) to Asia/Kathmandu."""
    if dt.tzinfo is None:
        raise ValueError("to_kathmandu requires an aware datetime")
    return dt.astimezone(KATHMANDU)


def start_of_day_npt(dt: datetime) -> datetime:
    """Midnight in Asia/Kathmandu for the NPT calendar day containing dt."""
    local = to_kathmandu(dt)
    return datetime.combine(local.date(), time.min, tzinfo=KATHMANDU)


def fiscal_year(d: date) -> str:
    """Nepali fiscal year (Shrawan 1 - Ashadh end) for an AD date, e.g. '2083/84'."""
    bs_year, bs_month, _ = to_bs(d)
    fy_start_year = bs_year if bs_month >= 4 else bs_year - 1
    return f"{fy_start_year}/{(fy_start_year + 1) % 100:02d}"
