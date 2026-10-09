"""Quiet-hours math (FR-6.3). Pure Python, no Django imports — rule 9.

Window is [21:00, 07:00) Asia/Kathmandu: a message due at 21:00 is held, one
due at 06:59 is held, one due at exactly 07:00 goes out immediately.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta

from core.domain.nptime import KATHMANDU, to_kathmandu

QUIET_START = time(21, 0)
QUIET_END = time(7, 0)


def is_quiet_hours(local_dt: datetime) -> bool:
    t = local_dt.time()
    return t >= QUIET_START or t < QUIET_END


def next_send_time(now_utc: datetime) -> datetime:
    """now_utc unchanged if outside quiet hours; otherwise the next 07:00
    Asia/Kathmandu, returned as a UTC-equivalent aware datetime.
    """
    local = to_kathmandu(now_utc)
    if not is_quiet_hours(local):
        return now_utc

    send_date = local.date() if local.time() < QUIET_END else local.date() + timedelta(days=1)
    send_at_local = datetime.combine(send_date, QUIET_END, tzinfo=KATHMANDU)
    return send_at_local.astimezone(now_utc.tzinfo)
