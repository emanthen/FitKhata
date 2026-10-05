"""Phone OTP: 6 digits, 5 min TTL, 3 sends/hour/phone, 5 wrong tries -> 15 min
lock. Backed by Redis (the same client Celery/Channels already use — no new
dependency) rather than the DB, since every key here is inherently
short-lived.
"""

from __future__ import annotations

import secrets

import redis
from django.conf import settings

OTP_LENGTH = 6
OTP_TTL_SECONDS = 5 * 60
SEND_LIMIT = 3
SEND_WINDOW_SECONDS = 60 * 60
MAX_WRONG_TRIES = 5
LOCK_SECONDS = 15 * 60

_redis = redis.from_url(settings.REDIS_URL, decode_responses=True)


class OtpRateLimited(Exception):
    def __init__(self, retry_after: int) -> None:
        self.retry_after = retry_after


class OtpLocked(Exception):
    def __init__(self, retry_after: int) -> None:
        self.retry_after = retry_after


def _code_key(phone: str) -> str:
    return f"otp:code:{phone}"


def _send_count_key(phone: str) -> str:
    return f"otp:sends:{phone}"


def _wrong_key(phone: str) -> str:
    return f"otp:wrong:{phone}"


def _lock_key(phone: str) -> str:
    return f"otp:lock:{phone}"


def send_otp(phone: str) -> str:
    """Generates and stores a code, returns it for the caller to send via SMS.
    Raises OtpRateLimited past SEND_LIMIT sends within SEND_WINDOW_SECONDS.
    """
    send_count_key = _send_count_key(phone)
    count = _redis.incr(send_count_key)
    if count == 1:
        _redis.expire(send_count_key, SEND_WINDOW_SECONDS)
    if count > SEND_LIMIT:
        raise OtpRateLimited(retry_after=_redis.ttl(send_count_key))

    code = "".join(secrets.choice("0123456789") for _ in range(OTP_LENGTH))
    _redis.set(_code_key(phone), code, ex=OTP_TTL_SECONDS)
    _redis.delete(_wrong_key(phone))
    return code


def verify_otp(phone: str, code: str) -> bool:
    """Returns True on a correct, not-yet-used code. Raises OtpLocked after
    MAX_WRONG_TRIES wrong attempts, for LOCK_SECONDS.
    """
    lock_ttl = _redis.ttl(_lock_key(phone))
    if lock_ttl and lock_ttl > 0:
        raise OtpLocked(retry_after=lock_ttl)

    stored = _redis.get(_code_key(phone))
    if stored is not None and secrets.compare_digest(str(stored), code):
        _redis.delete(_code_key(phone), _wrong_key(phone))
        return True

    wrong_key = _wrong_key(phone)
    wrong_count = _redis.incr(wrong_key)
    if wrong_count == 1:
        _redis.expire(wrong_key, OTP_TTL_SECONDS)
    if wrong_count >= MAX_WRONG_TRIES:
        _redis.set(_lock_key(phone), "1", ex=LOCK_SECONDS)
        _redis.delete(wrong_key, _code_key(phone))
        raise OtpLocked(retry_after=LOCK_SECONDS)

    return False
