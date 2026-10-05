from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.domain.qr import generate_token, payload_for, verify, window_for

VECTORS_PATH = Path(__file__).resolve().parents[4] / "shared" / "qr_vectors.json"


def _load_vectors() -> list[dict]:
    with VECTORS_PATH.open() as f:
        return json.load(f)


def test_vectors_file_exists_and_has_twenty_entries() -> None:
    vectors = _load_vectors()
    assert len(vectors) == 20


@pytest.mark.parametrize("vector", _load_vectors())
def test_generate_token_matches_vector(vector: dict) -> None:
    secret = bytes.fromhex(vector["secret_hex"])
    window = window_for(vector["unix_time"])
    assert generate_token(secret, window) == vector["expected_token"]


def test_window_for_is_30_second_buckets() -> None:
    assert window_for(0) == 0
    assert window_for(29) == 0
    assert window_for(30) == 1
    assert window_for(59) == 1
    assert window_for(60) == 2


def test_payload_format() -> None:
    secret = bytes.fromhex("00" * 32)
    payload = payload_for("KTM1", "KTM1-0001", secret, 1_700_000_000)
    gym_code, member_code, token = payload.split(".")
    assert gym_code == "KTM1"
    assert member_code == "KTM1-0001"
    assert len(token) == 10


def test_verify_accepts_current_window() -> None:
    secret = bytes.fromhex("11" * 32)
    now = 1_700_000_000
    token = generate_token(secret, window_for(now))
    assert verify(secret, token, now) is True


def test_verify_accepts_adjacent_windows() -> None:
    secret = bytes.fromhex("22" * 32)
    now = 1_700_000_000
    token = generate_token(secret, window_for(now))
    # One window (30s) either side of "now" still verifies.
    assert verify(secret, token, now - 30) is True
    assert verify(secret, token, now + 30) is True


def test_verify_rejects_stale_token_past_the_window() -> None:
    """Acceptance: a screenshot older than 60s is rejected. A token is only
    valid for windows w-1..w+1 (30s each) around generation time, so a token
    presented 90s+ later (two full windows away) must fail.
    """
    secret = bytes.fromhex("33" * 32)
    generated_at = 1_700_000_000
    token = generate_token(secret, window_for(generated_at))
    presented_at = generated_at + 90  # 3 windows later — outside w-1..w+1
    assert verify(secret, token, presented_at) is False


def test_verify_rejects_wrong_secret() -> None:
    now = 1_700_000_000
    token = generate_token(bytes.fromhex("55" * 32), window_for(now))
    assert verify(bytes.fromhex("66" * 32), token, now) is False
