from __future__ import annotations

import pytest

from accounts import otp

PHONE = "+9779811111111"


@pytest.fixture(autouse=True)
def _clean_redis():
    """Each test gets a clean slate — otp._redis is a real Redis connection
    (CI runs a real Redis service; see .github/workflows/ci.yml)."""
    otp._redis.flushdb()
    yield
    otp._redis.flushdb()


def test_send_otp_returns_a_6_digit_code():
    code = otp.send_otp(PHONE)
    assert len(code) == otp.OTP_LENGTH
    assert code.isdigit()


def test_send_otp_rate_limited_after_3_per_hour():
    for _ in range(otp.SEND_LIMIT):
        otp.send_otp(PHONE)
    with pytest.raises(otp.OtpRateLimited):
        otp.send_otp(PHONE)


def test_verify_otp_correct_code_succeeds():
    code = otp.send_otp(PHONE)
    assert otp.verify_otp(PHONE, code) is True


def test_verify_otp_is_one_time_use():
    code = otp.send_otp(PHONE)
    assert otp.verify_otp(PHONE, code) is True
    assert otp.verify_otp(PHONE, code) is False


def test_verify_otp_wrong_code_fails():
    otp.send_otp(PHONE)
    assert otp.verify_otp(PHONE, "000000") is False


def test_verify_otp_locks_after_5_wrong_tries():
    otp.send_otp(PHONE)
    for _ in range(otp.MAX_WRONG_TRIES - 1):
        assert otp.verify_otp(PHONE, "000000") is False
    with pytest.raises(otp.OtpLocked):
        otp.verify_otp(PHONE, "000000")


def test_verify_otp_locked_rejects_even_the_correct_code():
    code = otp.send_otp(PHONE)
    for _ in range(otp.MAX_WRONG_TRIES):
        try:
            otp.verify_otp(PHONE, "000000")
        except otp.OtpLocked:
            break
    with pytest.raises(otp.OtpLocked):
        otp.verify_otp(PHONE, code)
