"""Retry/fallback/dead-letter decision (FR-6.5/6.6 "provider failure falls
back to next channel"). Pure Python, no Django/Celery imports — rule 9.

A permanent error (bad phone number, expired push subscription, etc.) is
never worth retrying on the same channel — it falls back immediately. A
transient error (network blip, provider 5xx) retries with backoff up to
MAX_ATTEMPTS times on the same channel; only once that's exhausted does it
fall back. dead_letter is the true terminal state: retries exhausted (or a
permanent error) with no further channel to try.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

MAX_ATTEMPTS = 5
# Index 0 unused (attempt_count starts at 1 on the first failure) so
# BACKOFF_SECONDS[attempt_count] reads naturally at each call site.
BACKOFF_SECONDS = [0, 30, 120, 600, 1800, 3600]


class ProviderTransientError(Exception):
    """A retryable failure: network error, provider 5xx, rate limit, etc."""


class ProviderPermanentError(Exception):
    """A non-retryable failure: invalid destination, expired subscription,
    provider says the message itself can never be delivered.
    """


@dataclass(frozen=True)
class DeliveryDecision:
    action: Literal["delivered", "retry", "fallback", "dead_letter"]
    retry_countdown: int | None = None
    next_channel: str | None = None


def decide_delivery_outcome(
    *,
    attempt_count: int,
    success: bool,
    transient: bool,
    fallback_channel: str | None,
) -> DeliveryDecision:
    if success:
        return DeliveryDecision(action="delivered")

    if transient and attempt_count < MAX_ATTEMPTS:
        return DeliveryDecision(
            action="retry", retry_countdown=BACKOFF_SECONDS[attempt_count]
        )

    if fallback_channel:
        return DeliveryDecision(action="fallback", next_channel=fallback_channel)

    return DeliveryDecision(action="dead_letter")
