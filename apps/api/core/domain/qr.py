"""Gate QR token algorithm. Pure Python, no Django imports — must match
apps/web/lib/qr.ts byte-for-byte; both are tested against the same
shared/qr_vectors.json (CLAUDE.md rule 12).

window = floor(unix_seconds / 30)
mac = HMAC-SHA256(secret, window as 8-byte big-endian)
token = base32(mac)[0:10]
payload = f"{gym_code}.{member_code}.{token}"
verify accepts windows (w-1, w, w+1) — a 30s-aligned token stays valid for
up to ~60-90s of clock skew/scan latency either side.
"""

from __future__ import annotations

import base64
import hashlib
import hmac

WINDOW_SECONDS = 30
TOKEN_LENGTH = 10


def window_for(unix_seconds: int) -> int:
    return unix_seconds // WINDOW_SECONDS


def generate_token(secret: bytes, window: int) -> str:
    mac = hmac.new(secret, window.to_bytes(8, "big"), hashlib.sha256).digest()
    return base64.b32encode(mac).decode("ascii")[:TOKEN_LENGTH]


def payload_for(gym_code: str, member_code: str, secret: bytes, unix_seconds: int) -> str:
    token = generate_token(secret, window_for(unix_seconds))
    return f"{gym_code}.{member_code}.{token}"


def verify(secret: bytes, token: str, unix_seconds: int) -> bool:
    """True if token matches this secret for window w-1, w, or w+1.

    gym_code/member_code aren't part of the MAC (only `window` is) — they're
    a lookup key in the payload string, not a binding. The caller looks up
    *which* member's secret to verify against via (gym_code, member_code)
    parsed from the payload; a wrong/forged member_code simply fails to
    verify because the caller fetches a different (wrong) secret for it,
    not because this function checks the codes itself.
    """
    window = window_for(unix_seconds)
    for w in (window - 1, window, window + 1):
        if hmac.compare_digest(generate_token(secret, w), token):
            return True
    return False
