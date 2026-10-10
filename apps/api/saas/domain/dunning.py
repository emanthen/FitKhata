"""Pure dunning state-transition function — no Django imports, see rule 9.

Only ACTIVE/GRACE/READ_ONLY ever auto-transition here; TRIAL and CANCELLED
are untouched by the automatic sweep (trial conversion and voluntary
cancellation are separate, explicit actions — see saas/services.py).
Payment restoring a subscription to ACTIVE is handled by
confirm_saas_invoice_payment, not this function — this only ever moves a
subscription further into dunning, never back out of it.
"""

from __future__ import annotations

READ_ONLY_AT_DAY = 8
SUSPENDED_AT_DAY = 30


def next_status(current_status: str, days_since_invoice: int) -> str | None:
    """Returns the new status, or None if nothing should change."""
    if current_status == "active":
        return "grace"
    if current_status == "grace" and days_since_invoice >= READ_ONLY_AT_DAY:
        return "read_only"
    if current_status == "read_only" and days_since_invoice >= SUSPENDED_AT_DAY:
        return "suspended"
    return None
