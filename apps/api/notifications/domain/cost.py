"""Broadcast NPR cost math (FR-6.4). Pure Python, no Django imports — rule 9.

Only SMS has a per-message cost this phase (the SmsWallet it debits, FR-11.5).
WhatsApp's conversation-based pricing and push/email's effectively-free cost
aren't tracked yet — out of scope, not an oversight.
"""

from __future__ import annotations

from decimal import Decimal


def broadcast_cost_npr(recipient_count: int, channel: str, sms_cost_npr: Decimal) -> Decimal:
    if channel != "sms":
        return Decimal("0.00")
    return (Decimal(recipient_count) * sms_cost_npr).quantize(Decimal("0.01"))
