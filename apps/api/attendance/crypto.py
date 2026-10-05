"""Per-device AES-GCM encryption for the gate snapshot's qr_secret field.

The key is derived (HKDF-SHA256) from the device's *raw* token on every
request, never persisted — the server only ever stores device_key_hash
(SHA-256 of the token, for auth lookup). The raw token necessarily passes
through on every authenticated request (standard bearer-token behaviour),
so attendance.authentication.GateDeviceAuthentication has it available each
time to re-derive the same key.
"""

from __future__ import annotations

import os

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

_HKDF_INFO = b"fitkhata-gate-device-key"
_AES_KEY_LENGTH = 32
_NONCE_LENGTH = 12


def derive_device_key(raw_token: str) -> bytes:
    hkdf = HKDF(algorithm=hashes.SHA256(), length=_AES_KEY_LENGTH, salt=None, info=_HKDF_INFO)
    return hkdf.derive(raw_token.encode("utf-8"))


def encrypt_for_device(key: bytes, plaintext: bytes) -> dict[str, str]:
    """Returns {"nonce": hex, "ciphertext": hex} — both needed by the
    device to decrypt (AES-GCM ciphertext includes the auth tag already).
    """
    nonce = os.urandom(_NONCE_LENGTH)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    return {"nonce": nonce.hex(), "ciphertext": ciphertext.hex()}
