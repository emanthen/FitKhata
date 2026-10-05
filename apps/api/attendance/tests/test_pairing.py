from __future__ import annotations

import pytest

from attendance.pairing import generate_pairing_code, redeem_pairing_code
from core.context import system_context
from gyms.models import Gym, Organization

pytestmark = pytest.mark.django_db


@pytest.fixture
def gym():
    with system_context():
        org = Organization.objects.create(name="Pairing Test Org")
        return Gym.objects.create(org=org, code="PAIR1", name="Pairing Test Gym")


def test_redeem_returns_the_right_gym(gym):
    code = generate_pairing_code(gym)
    redeemed = redeem_pairing_code(code)
    assert redeemed is not None
    assert redeemed.pk == gym.pk


def test_code_is_one_time_use(gym):
    code = generate_pairing_code(gym)
    redeem_pairing_code(code)
    assert redeem_pairing_code(code) is None


def test_unknown_code_returns_none():
    assert redeem_pairing_code("000000") is None


def test_code_is_six_digits(gym):
    code = generate_pairing_code(gym)
    assert len(code) == 6
    assert code.isdigit()
