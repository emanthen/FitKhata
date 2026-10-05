"""Gate device pairing codes: one-time 6-digit codes, short TTL. Same Redis-
backed shape as accounts/otp.py — a pairing code is exactly as short-lived
and single-use as an OTP code, just mapping to a gym instead of verifying a
phone.
"""

from __future__ import annotations

import secrets

import redis
from django.conf import settings

from core.context import system_context
from gyms.models import Gym

PAIRING_CODE_LENGTH = 6
PAIRING_CODE_TTL_SECONDS = 10 * 60

_redis = redis.from_url(settings.REDIS_URL, decode_responses=True)


def _pairing_key(code: str) -> str:
    return f"gate:pair:{code}"


def generate_pairing_code(gym: Gym) -> str:
    code = "".join(secrets.choice("0123456789") for _ in range(PAIRING_CODE_LENGTH))
    _redis.set(_pairing_key(code), str(gym.pk), ex=PAIRING_CODE_TTL_SECONDS)
    return code


def redeem_pairing_code(code: str) -> Gym | None:
    """One-time: deletes the code on lookup regardless of outcome, so a
    guessed-but-stale code can't be retried.
    """
    key = _pairing_key(code)
    gym_id = _redis.get(key)
    _redis.delete(key)
    if gym_id is None:
        return None
    with system_context():
        return Gym.objects.filter(pk=str(gym_id)).first()
