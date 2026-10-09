from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from notifications.domain.quiet_hours import next_send_time

UTC = ZoneInfo("UTC")
KTM = ZoneInfo("Asia/Kathmandu")


def _ktm(y, m, d, hh, mm) -> datetime:
    return datetime(y, m, d, hh, mm, tzinfo=KTM)


def test_just_before_quiet_start_is_unchanged():
    now = _ktm(2026, 1, 15, 20, 59)
    assert next_send_time(now) == now


def test_at_quiet_start_shifts_to_next_morning():
    now = _ktm(2026, 1, 15, 21, 0)
    result = next_send_time(now)
    assert result.astimezone(KTM) == _ktm(2026, 1, 16, 7, 0)


def test_late_night_shifts_to_next_morning():
    now = _ktm(2026, 1, 15, 23, 30)
    result = next_send_time(now)
    assert result.astimezone(KTM) == _ktm(2026, 1, 16, 7, 0)


def test_just_before_quiet_end_shifts_to_same_morning():
    now = _ktm(2026, 1, 15, 6, 59)
    result = next_send_time(now)
    assert result.astimezone(KTM) == _ktm(2026, 1, 15, 7, 0)


def test_at_quiet_end_is_unchanged():
    now = _ktm(2026, 1, 15, 7, 0)
    assert next_send_time(now) == now


def test_midday_is_unchanged():
    now = _ktm(2026, 1, 15, 13, 0)
    assert next_send_time(now) == now


def test_accepts_utc_input_and_returns_utc():
    now_utc = datetime(2026, 1, 15, 16, 0, tzinfo=UTC)  # 21:45 NPT
    result = next_send_time(now_utc)
    assert result.tzinfo == UTC
    assert result.astimezone(KTM) == _ktm(2026, 1, 16, 7, 0)
