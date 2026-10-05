"""Plan.access_hours schema + check (FR-3.9). Pure, no Django imports.

Schema:
    {}                                    -> unrestricted (default)
    {"always": true}                      -> unrestricted, explicit
    {"windows": [{"day": "mon", "start": "06:00", "end": "22:00"}, ...]}
        -> restricted to the union of listed day/time windows. "day" is a
        lowercase 3-letter code (mon..sun); "start"/"end" are "HH:MM",
        inclusive on both ends, same-day only (no overnight-spanning
        windows this phase — split into two entries for e.g. 22:00-02:00).
"""

from __future__ import annotations

from datetime import datetime, time
from typing import Any

_DAY_CODES = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


def is_within_access_hours(access_hours: dict[str, Any], now_kathmandu: datetime) -> bool:
    windows = access_hours.get("windows")
    if not windows:
        return True

    day_code = _DAY_CODES[now_kathmandu.weekday()]
    current = now_kathmandu.time()
    for window in windows:
        if window.get("day") != day_code:
            continue
        start = time.fromisoformat(window["start"])
        end = time.fromisoformat(window["end"])
        if start <= current <= end:
            return True
    return False
