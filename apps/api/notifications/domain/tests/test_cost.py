from __future__ import annotations

from decimal import Decimal

from notifications.domain.cost import broadcast_cost_npr


def test_sms_cost_is_recipients_times_per_message_cost():
    assert broadcast_cost_npr(100, "sms", Decimal("1.50")) == Decimal("150.00")


def test_zero_recipients_costs_nothing():
    assert broadcast_cost_npr(0, "sms", Decimal("1.50")) == Decimal("0.00")


def test_non_sms_channels_are_free_this_phase():
    assert broadcast_cost_npr(500, "whatsapp", Decimal("1.50")) == Decimal("0.00")
    assert broadcast_cost_npr(500, "push", Decimal("1.50")) == Decimal("0.00")
    assert broadcast_cost_npr(500, "email", Decimal("1.50")) == Decimal("0.00")
