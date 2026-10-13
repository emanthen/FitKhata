from __future__ import annotations

import hashlib
import hmac
import json
from unittest.mock import Mock, patch

import pytest
import requests

from core.context import system_context
from core.crypto import encrypt_bytes
from gyms.models import Gym, Organization
from publicapi.models import WebhookDelivery, WebhookSubscription
from publicapi.services import dispatch_webhook_event
from publicapi.tasks import deliver_webhook, sign_payload

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _skip_ssrf_check_by_default(monkeypatch):
    """Every test below exercises retry/signature/dispatch logic, not the
    SSRF check itself (see test_url_safety.py and the two tests at the
    bottom of this file for that) — a real DNS lookup for "example.com"
    on every test run here would be an unnecessary live-network
    dependency for behavior these tests aren't about.
    """
    monkeypatch.setattr("publicapi.tasks.assert_safe_webhook_url", lambda url: None)


@pytest.fixture
def org():
    with system_context():
        return Organization.objects.create(name="Webhook Test Org")


@pytest.fixture
def gym(org):
    with system_context():
        return Gym.objects.create(org=org, code="WHK1", name="Webhook Test Gym")


@pytest.fixture
def subscription(org):
    with system_context():
        return WebhookSubscription.objects.create(
            org=org,
            url="https://example.com/hooks/fitkhata",
            secret_encrypted=encrypt_bytes(b"shh-its-a-secret"),
            events=[WebhookSubscription.Event.MEMBER_CREATED],
        )


def _delivery_for(subscription, event="member.created", payload=None):
    with system_context():
        return WebhookDelivery.objects.create(
            subscription=subscription, event=event, payload=payload or {"member_id": 1}
        )


# --- sign_payload ------------------------------------------------------


def test_sign_payload_matches_a_manually_computed_hmac():
    body = json.dumps({"a": 1}, sort_keys=True).encode("utf-8")
    expected = hmac.new(b"my-secret", body, hashlib.sha256).hexdigest()

    assert sign_payload("my-secret", body) == f"sha256={expected}"


def test_sign_payload_changes_when_the_body_changes():
    sig_a = sign_payload("my-secret", b'{"a":1}')
    sig_b = sign_payload("my-secret", b'{"a":2}')

    assert sig_a != sig_b


def test_sign_payload_changes_when_the_secret_changes():
    sig_a = sign_payload("secret-one", b'{"a":1}')
    sig_b = sign_payload("secret-two", b'{"a":1}')

    assert sig_a != sig_b


# --- deliver_webhook -----------------------------------------------------


def test_deliver_webhook_signs_the_request_with_the_subscriptions_secret(subscription):
    delivery = _delivery_for(subscription, payload={"member_id": 42})

    with system_context(), patch("publicapi.tasks.requests.post") as mock_post:
        mock_post.return_value = Mock(status_code=200, text="ok")
        deliver_webhook(str(delivery.pk))

    sent_body = mock_post.call_args.kwargs["data"]
    sent_headers = mock_post.call_args.kwargs["headers"]
    expected_signature = sign_payload("shh-its-a-secret", sent_body)

    assert sent_headers["X-FitKhata-Signature"] == expected_signature
    assert sent_headers["X-FitKhata-Event"] == "member.created"


def test_deliver_webhook_marks_delivered_on_2xx(subscription):
    delivery = _delivery_for(subscription)

    with system_context(), patch("publicapi.tasks.requests.post") as mock_post:
        mock_post.return_value = Mock(status_code=200, text="ok")
        deliver_webhook(str(delivery.pk))

    with system_context():
        delivery.refresh_from_db()
    assert delivery.status == WebhookDelivery.Status.DELIVERED
    assert delivery.attempt_count == 1
    assert delivery.response_status == 200


def test_deliver_webhook_retries_on_non_2xx_and_stays_pending(subscription):
    delivery = _delivery_for(subscription)

    with (
        system_context(),
        patch("publicapi.tasks.requests.post") as mock_post,
        # CELERY_TASK_ALWAYS_EAGER + EAGER_PROPAGATES: self.retry() re-raises
        # synchronously rather than actually re-queueing -- same pattern as
        # notifications/tests/test_tasks.py.
        pytest.raises(Exception, match="status 500"),
    ):
        mock_post.return_value = Mock(status_code=500, text="server error")
        deliver_webhook(str(delivery.pk))

    with system_context():
        delivery.refresh_from_db()
    assert delivery.status == WebhookDelivery.Status.PENDING
    assert delivery.attempt_count == 1
    assert delivery.response_status == 500


def test_deliver_webhook_retries_on_network_error(subscription):
    delivery = _delivery_for(subscription)

    with (
        system_context(),
        patch("publicapi.tasks.requests.post", side_effect=requests.ConnectionError("down")),
        pytest.raises(Exception, match="down"),
    ):
        deliver_webhook(str(delivery.pk))

    with system_context():
        delivery.refresh_from_db()
    assert delivery.status == WebhookDelivery.Status.PENDING
    assert delivery.attempt_count == 1
    assert delivery.response_status is None


def test_deliver_webhook_gives_up_after_max_attempts(subscription):
    delivery = _delivery_for(subscription)
    with system_context():
        delivery.attempt_count = WebhookDelivery.MAX_ATTEMPTS - 1
        delivery.save(update_fields=["attempt_count"])

    with system_context(), patch("publicapi.tasks.requests.post") as mock_post:
        mock_post.return_value = Mock(status_code=500, text="server error")
        # No retry raised this time -- attempt_count has just reached MAX_ATTEMPTS.
        deliver_webhook(str(delivery.pk))

    with system_context():
        delivery.refresh_from_db()
    assert delivery.status == WebhookDelivery.Status.FAILED
    assert delivery.attempt_count == WebhookDelivery.MAX_ATTEMPTS


# --- dispatch_webhook_event -----------------------------------------------


def test_dispatch_webhook_event_only_fires_for_subscribed_events(subscription, org):
    with (
        system_context(),
        patch("publicapi.tasks.deliver_webhook.delay") as mock_delay,
    ):
        dispatch_webhook_event(org, "payment.completed", {"x": 1})  # not subscribed
        assert mock_delay.call_count == 0

        dispatch_webhook_event(org, "member.created", {"x": 1})  # subscribed
        assert mock_delay.call_count == 1

    with system_context():
        assert WebhookDelivery.objects.filter(subscription=subscription).count() == 1


# --- SSRF: re-checked at delivery time, not just subscription-create ------


def test_create_serializer_rejects_an_unsafe_url(monkeypatch):
    from publicapi.serializers import WebhookSubscriptionCreateSerializer
    from publicapi.url_safety import UnsafeWebhookUrl

    def _always_unsafe(url):
        raise UnsafeWebhookUrl("resolves to a private address")

    monkeypatch.setattr("publicapi.serializers.assert_safe_webhook_url", _always_unsafe)
    serializer = WebhookSubscriptionCreateSerializer(
        data={"url": "https://internal.example/hook", "events": ["member.created"], "secret": "x"}
    )

    assert serializer.is_valid() is False
    assert "url" in serializer.errors


def test_deliver_webhook_fails_closed_if_the_url_is_unsafe_at_delivery_time(subscription):
    """The DNS-rebinding case: the URL passed its create-time check, but
    the hostname now resolves somewhere unsafe by the time delivery
    actually runs — must reject outright, no retry, and never call
    requests.post at all.
    """
    from publicapi.url_safety import UnsafeWebhookUrl

    delivery = _delivery_for(subscription)

    with (
        system_context(),
        patch(
            "publicapi.tasks.assert_safe_webhook_url",
            side_effect=UnsafeWebhookUrl("resolves to 169.254.169.254"),
        ),
        patch("publicapi.tasks.requests.post") as mock_post,
    ):
        deliver_webhook(str(delivery.pk))

    mock_post.assert_not_called()
    with system_context():
        delivery.refresh_from_db()
    assert delivery.status == WebhookDelivery.Status.FAILED
    assert "169.254.169.254" in delivery.response_body


def test_deliver_webhook_does_not_follow_redirects(subscription):
    """allow_redirects=False: a 3xx response must be treated as a plain
    non-2xx (retried/failed on its own terms), never silently followed to
    a target that was never checked by assert_safe_webhook_url.
    """
    delivery = _delivery_for(subscription)

    with (
        system_context(),
        patch("publicapi.tasks.requests.post") as mock_post,
        pytest.raises(Exception, match="status 302"),
    ):
        mock_post.return_value = Mock(status_code=302, text="redirecting")
        deliver_webhook(str(delivery.pk))

    assert mock_post.call_args.kwargs["allow_redirects"] is False
    with system_context():
        delivery.refresh_from_db()
    assert delivery.status == WebhookDelivery.Status.PENDING
    assert delivery.response_status == 302


def test_dispatch_webhook_event_skips_inactive_subscriptions(subscription, org):
    with system_context():
        subscription.is_active = False
        subscription.save(update_fields=["is_active"])

    with system_context(), patch("publicapi.tasks.deliver_webhook.delay") as mock_delay:
        dispatch_webhook_event(org, "member.created", {"x": 1})

    assert mock_delay.call_count == 0
