from __future__ import annotations

from notifications.domain.retry import BACKOFF_SECONDS, decide_delivery_outcome


def test_success_is_delivered_regardless_of_attempt_count():
    decision = decide_delivery_outcome(
        attempt_count=3, success=True, transient=False, fallback_channel="sms"
    )
    assert decision.action == "delivered"


def test_transient_failure_retries_with_backoff():
    decision = decide_delivery_outcome(
        attempt_count=1, success=False, transient=True, fallback_channel="sms"
    )
    assert decision.action == "retry"
    assert decision.retry_countdown == BACKOFF_SECONDS[1]


def test_permanent_failure_falls_back_immediately_without_retrying():
    decision = decide_delivery_outcome(
        attempt_count=1, success=False, transient=False, fallback_channel="sms"
    )
    assert decision.action == "fallback"
    assert decision.next_channel == "sms"


def test_transient_failure_falls_back_once_retries_are_exhausted():
    decision = decide_delivery_outcome(
        attempt_count=5, success=False, transient=True, fallback_channel="whatsapp"
    )
    assert decision.action == "fallback"
    assert decision.next_channel == "whatsapp"


def test_permanent_failure_with_no_fallback_channel_is_dead_lettered():
    decision = decide_delivery_outcome(
        attempt_count=1, success=False, transient=False, fallback_channel=None
    )
    assert decision.action == "dead_letter"


def test_exhausted_transient_failure_with_no_fallback_channel_is_dead_lettered():
    decision = decide_delivery_outcome(
        attempt_count=5, success=False, transient=True, fallback_channel=None
    )
    assert decision.action == "dead_letter"
