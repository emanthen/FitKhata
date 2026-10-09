"""Freeze/unfreeze expiry math (FR-5.8/5.9). Pure Python, no Django imports.

Inclusive-day convention (start and end both count), matching
members/domain/renewal.py's existing convention -- a freeze from day 1 to
day 1 is a single frozen day, not zero.
"""

from __future__ import annotations

from datetime import date, timedelta


def apply_freeze(expiry: date, start: date, end: date) -> tuple[date, int]:
    """Returns (new_expiry, days_frozen). new_expiry = expiry + days_frozen."""
    days = (end - start).days + 1
    return expiry + timedelta(days=days), days


def revert_freeze(frozen_expiry: date, days: int) -> date:
    """Inverse of apply_freeze's first return value -- restores the exact
    previous expiry given the same `days` apply_freeze computed.
    """
    return frozen_expiry - timedelta(days=days)
