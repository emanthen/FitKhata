"""Fernet encryption for values that must be unreadable at rest. Rule 10:
same FIELD_ENCRYPTION_KEY env var used for per-gym payment keys — one key,
one env var, reused here for Member.qr_secret rather than inventing a
second scheme.
"""

from __future__ import annotations

from cryptography.fernet import Fernet
from django.conf import settings


def _fernet() -> Fernet:
    return Fernet(settings.FIELD_ENCRYPTION_KEY)


def encrypt_bytes(data: bytes) -> bytes:
    return _fernet().encrypt(data)


def decrypt_bytes(data: bytes) -> bytes:
    return _fernet().decrypt(data)
