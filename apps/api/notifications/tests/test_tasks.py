from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest

from core.context import system_context
from gyms.models import Gym, Organization
from members.services import register_member
from notifications.domain.retry import ProviderTransientError
from notifications.models import Notification, PushSubscription, SmsWallet
from notifications.tasks import (
    send_birthday_notifications,
    send_push_notification,
    send_sms_notification,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def gym():
    with system_context():
        org = Organization.objects.create(name="Notifications Task Test Org")
        gym = Gym.objects.create(org=org, code="NTT1", name="Notifications Task Test Gym")
        SmsWallet.objects.create(org=org, balance_npr=Decimal("1000.00"))
        return gym


@pytest.fixture
def member(gym):
    with system_context():
        return register_member(gym, full_name="Ram Shrestha", phone="+9779800000001")


def test_send_sms_notification_marks_sent_on_success(member):
    with system_context():
        notification = Notification.objects.create(
            org=member.org,
            gym=member.gym,
            member=member,
            channel="sms",
            template_key="payment_receipt",
            language=member.language,
            payload={"body": "Test message"},
        )
        send_sms_notification(notification.pk)
        notification.refresh_from_db()

    assert notification.status == Notification.Status.SENT
    assert notification.cost_npr == Decimal("1.50")


def test_send_push_notification_falls_back_when_no_subscription_exists(member):
    with system_context():
        member.gym.settings = {
            **member.gym.settings,
            "notification_channel_order": ["push", "sms"],
        }
        member.gym.save(update_fields=["settings"])

        notification = Notification.objects.create(
            org=member.org,
            gym=member.gym,
            member=member,
            channel="push",
            template_key="payment_receipt",
            language=member.language,
            payload={"body": "Test message", "context": {}},
        )
        send_push_notification(notification.pk)
        notification.refresh_from_db()

        fallback = Notification.objects.get(fallback_of=notification)

    assert notification.status == Notification.Status.FAILED
    assert fallback.channel == "sms"


def test_send_push_notification_retries_on_a_transient_provider_error(member):
    with system_context():
        PushSubscription.objects.create(
            org=member.org,
            gym=member.gym,
            member=member,
            endpoint=f"https://fcm.googleapis.com/fcm/send/{uuid.uuid4()}",
            keys={"p256dh": "fake-p256dh", "auth": "fake-auth"},
        )
        notification = Notification.objects.create(
            org=member.org,
            gym=member.gym,
            member=member,
            channel="push",
            template_key="payment_receipt",
            language=member.language,
            payload={"body": "Test message", "context": {}},
        )

    with (
        system_context(),
        patch(
            "notifications.tasks.push_provider.send",
            side_effect=ProviderTransientError("network blip"),
        ),
        pytest.raises(Exception, match="network blip"),
    ):
        # CELERY_TASK_ALWAYS_EAGER + EAGER_PROPAGATES: self.retry() raises
        # the original exception synchronously rather than actually
        # re-queueing — this just confirms the task attempted a retry
        # instead of silently swallowing a transient failure.
        send_push_notification(notification.pk)

    with system_context():
        notification.refresh_from_db()
    assert notification.attempt_count == 1
    assert notification.status == Notification.Status.QUEUED


def test_send_birthday_notifications_fires_only_for_matching_dob(gym):
    with system_context():
        birthday_member = register_member(
            gym, full_name="Birthday Person", phone="+9779800000010", dob=date(1990, 3, 15)
        )
        other_member = register_member(
            gym, full_name="Not Today", phone="+9779800000011", dob=date(1990, 6, 1)
        )
        Notification.objects.all().delete()

    frozen_now = datetime(2026, 3, 15, 10, 0, tzinfo=ZoneInfo("Asia/Kathmandu"))
    with patch("notifications.tasks.timezone.now", return_value=frozen_now):
        send_birthday_notifications()

    with system_context():
        assert Notification.objects.filter(
            member=birthday_member, template_key="birthday"
        ).exists()
        assert not Notification.objects.filter(
            member=other_member, template_key="birthday"
        ).exists()
