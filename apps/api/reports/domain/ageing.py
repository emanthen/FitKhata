"""Dues ageing buckets (FR-10.6). Pure Python, no Django imports — rule 9."""

from __future__ import annotations

from typing import Literal

AgeingBucket = Literal["0-30", "31-60", "60+"]


def bucket_dues_ageing(days_outstanding: int) -> AgeingBucket:
    if days_outstanding <= 30:
        return "0-30"
    if days_outstanding <= 60:
        return "31-60"
    return "60+"
