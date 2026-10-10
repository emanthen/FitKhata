"""Roster conflict detection. Pure Python, no Django imports — rule 9."""

from __future__ import annotations

from datetime import date, time


def overlaps(a: tuple[date, time, time], b: tuple[date, time, time]) -> bool:
    """Each shift is (date, start, end). Different dates never conflict.
    Touching-but-not-overlapping (one shift's end == the other's start) is
    NOT a conflict — strict inequality both ways.
    """
    a_date, a_start, a_end = a
    b_date, b_start, b_end = b
    if a_date != b_date:
        return False
    return a_start < b_end and b_start < a_end
