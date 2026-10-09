"""Pure streak math over distinct visit dates (rule 9) -- no ORM here, see
attendance/views.py::MemberAttendanceCalendarView for the caller that builds
the distinct-date list from Attendance rows.
"""

from __future__ import annotations

from datetime import date, timedelta
from itertools import pairwise


def compute_streaks(visit_dates: list[date]) -> tuple[int, int]:
    """visit_dates: distinct calendar dates with >=1 check-in, any order.

    Returns (current_streak, longest_streak) counted in consecutive-day
    runs. current_streak is 0 if the most recent visit isn't today or
    yesterday -- a lapsed streak isn't "current" even if it was once long.
    """
    if not visit_dates:
        return 0, 0

    days = sorted(set(visit_dates))

    longest = 1
    run = 1
    for prev, curr in pairwise(days):
        if curr - prev == timedelta(days=1):
            run += 1
        else:
            run = 1
        longest = max(longest, run)

    most_recent = days[-1]
    if date.today() - most_recent > timedelta(days=1):
        return 0, longest

    current = 1
    for prev, curr in pairwise(reversed(days)):
        if prev - curr == timedelta(days=1):
            current += 1
        else:
            break
    return current, longest
