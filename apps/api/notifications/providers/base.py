"""Shared exception types every provider raises — notifications/domain/retry.py's
decide_delivery_outcome() branches on isinstance(exc, ProviderPermanentError),
so a provider's choice of which one to raise IS the retry/fallback decision.
"""

from __future__ import annotations

from notifications.domain.retry import ProviderPermanentError, ProviderTransientError

__all__ = ["ProviderPermanentError", "ProviderTransientError"]
