"""Late-arrival detection. Pure Python, no Django imports — rule 9."""

from __future__ import annotations

from datetime import datetime, time, timedelta


def is_late(clock_in: datetime, shift_start: time, grace_minutes: int) -> bool:
    """True if clock_in is later than shift_start + grace, on clock_in's
    own calendar day (a shift starting 23:50 and a clock_in at 00:05 the
    next day is a separate concern — not handled here).
    """
    deadline = datetime.combine(clock_in.date(), shift_start, tzinfo=clock_in.tzinfo) + timedelta(
        minutes=grace_minutes
    )
    return clock_in > deadline
