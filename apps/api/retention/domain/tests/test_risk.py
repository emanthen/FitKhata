from __future__ import annotations

from retention.domain.risk import NORMAL, RED_LIST, WARNING, risk_state

WARNING_DAYS = 7
RED_DAYS = 10


def test_below_warning_threshold_is_normal():
    assert risk_state(WARNING_DAYS - 1, WARNING_DAYS, RED_DAYS) == NORMAL


def test_exactly_at_warning_threshold_is_warning():
    assert risk_state(WARNING_DAYS, WARNING_DAYS, RED_DAYS) == WARNING


def test_just_below_red_threshold_is_still_warning():
    assert risk_state(RED_DAYS - 1, WARNING_DAYS, RED_DAYS) == WARNING


def test_exactly_at_red_threshold_is_red_list():
    assert risk_state(RED_DAYS, WARNING_DAYS, RED_DAYS) == RED_LIST


def test_far_past_red_threshold_is_red_list():
    assert risk_state(RED_DAYS + 100, WARNING_DAYS, RED_DAYS) == RED_LIST


def test_zero_days_absent_is_normal():
    assert risk_state(0, WARNING_DAYS, RED_DAYS) == NORMAL
