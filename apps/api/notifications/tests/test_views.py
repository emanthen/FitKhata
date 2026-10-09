from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from decimal import Decimal

import pytest
from django.core import signing
from rest_framework.test import APIClient

from accounts.models import StaffRole, User
from accounts.tokens import issue_tokens_for_user
from core.context import system_context
from gyms.models import Gym, Organization
from members.models import Member
from members.services import register_member
from notifications.models import Announcement, Notification, PushSubscription, SmsWallet

pytestmark = pytest.mark.django_db

PASS_SALT = "attendance.member-pass"


def _client_for(user: User, gym: Gym) -> APIClient:
    tokens = issue_tokens_for_user(user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}", HTTP_X_GYM_ID=str(gym.pk))
    return client


@pytest.fixture
def setup():
    with system_context():
        org = Organization.objects.create(name="Notifications View Test Org")
        gym = Gym.objects.create(org=org, code="NVT1", name="Notifications View Test Gym")
        SmsWallet.objects.create(org=org, balance_npr=Decimal("1000.00"))
        owner = User.objects.create_user(phone="+9774000001001", password="x")
        StaffRole.objects.create(user=owner, org=org, gym=gym, role=StaffRole.Role.OWNER)
        manager = User.objects.create_user(phone="+9774000001002", password="x")
        StaffRole.objects.create(user=manager, org=org, gym=gym, role=StaffRole.Role.MANAGER)
        front_desk = User.objects.create_user(phone="+9774000001003", password="x")
        StaffRole.objects.create(user=front_desk, org=org, gym=gym, role=StaffRole.Role.FRONT_DESK)
        member = register_member(gym, full_name="Test Member", phone="+9779800099001")
    return org, gym, owner, manager, front_desk, member


# --- WhatsApp webhook ---------------------------------------------------------


def _sign(body: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def test_webhook_verify_challenge(settings):
    settings.WHATSAPP_WEBHOOK_VERIFY_TOKEN = "verify-me"
    client = APIClient()
    response = client.get(
        "/api/v1/notifications/whatsapp/webhook",
        {"hub.verify_token": "verify-me", "hub.challenge": "12345"},
    )
    assert response.status_code == 200
    assert response.content == b"12345"


def test_webhook_rejects_tampered_payload(settings):
    settings.WHATSAPP_APP_SECRET = "webhook-secret"
    client = APIClient()
    body = json.dumps({"entry": []}).encode("utf-8")
    bad_signature = _sign(b"something else entirely", "webhook-secret")

    response = client.post(
        "/api/v1/notifications/whatsapp/webhook",
        data=body,
        content_type="application/json",
        HTTP_X_HUB_SIGNATURE_256=bad_signature,
    )
    assert response.status_code == 403


def test_webhook_updates_notification_status_on_valid_signature(settings, setup):
    settings.WHATSAPP_APP_SECRET = "webhook-secret"
    _org, gym, _owner, _manager, _front_desk, member = setup

    with system_context():
        notification = Notification.objects.create(
            org=gym.org,
            gym=gym,
            member=member,
            channel="whatsapp",
            template_key="payment_receipt",
            language=member.language,
            provider_ref="wamid.TEST123",
            status=Notification.Status.SENT,
        )

    payload = {
        "entry": [
            {
                "changes": [
                    {"value": {"statuses": [{"id": "wamid.TEST123", "status": "delivered"}]}}
                ]
            }
        ]
    }
    body = json.dumps(payload).encode("utf-8")
    signature = _sign(body, "webhook-secret")

    client = APIClient()
    response = client.post(
        "/api/v1/notifications/whatsapp/webhook",
        data=body,
        content_type="application/json",
        HTTP_X_HUB_SIGNATURE_256=signature,
    )

    assert response.status_code == 200
    with system_context():
        notification.refresh_from_db()
    assert notification.status == Notification.Status.DELIVERED
    assert notification.delivered_at is not None


# --- Broadcast (FR-6.4) -------------------------------------------------------


def test_front_desk_cannot_estimate_a_broadcast(setup):
    _org, gym, _owner, _manager, front_desk, _member = setup
    client = _client_for(front_desk, gym)
    response = client.post(
        "/api/v1/notifications/broadcasts/estimate",
        {"segment": "expired", "channel": "sms"},
        format="json",
    )
    assert response.status_code == 403


def test_manager_can_estimate_and_send_a_broadcast(setup):
    _org, gym, _owner, manager, _front_desk, member = setup
    with system_context():
        member.status = Member.Status.EXPIRED
        member.save(update_fields=["status"])

    client = _client_for(manager, gym)
    estimate = client.post(
        "/api/v1/notifications/broadcasts/estimate",
        {"segment": "expired", "channel": "sms"},
        format="json",
    )
    assert estimate.status_code == 200, estimate.content
    assert estimate.json()["recipient_count"] == 1

    sent = client.post(
        "/api/v1/notifications/broadcasts/",
        {
            "segment": "expired",
            "channel": "sms",
            "body_ne": "ne body",
            "body_en": "en body",
        },
        format="json",
    )
    assert sent.status_code == 201, sent.content
    assert sent.json()["recipient_count"] == 1


# --- Member-facing: push subscribe + announcements ----------------------------


def test_member_can_register_a_push_subscription(setup):
    _org, _gym, _owner, _manager, _front_desk, member = setup
    token = signing.dumps({"member_id": member.pk}, salt=PASS_SALT)
    client = APIClient()

    response = client.post(
        f"/api/v1/m/pass/{token}/push-subscribe",
        {
            "endpoint": f"https://fcm.googleapis.com/fcm/send/{uuid.uuid4()}",
            "keys": {"p256dh": "x", "auth": "y"},
        },
        format="json",
    )

    assert response.status_code == 201, response.content
    with system_context():
        assert PushSubscription.objects.filter(member=member).exists()


def test_member_sees_only_active_announcements_in_their_own_language(setup):
    _org, gym, _owner, _manager, _front_desk, member = setup
    with system_context():
        Announcement.objects.create(
            org=gym.org,
            gym=gym,
            title="Active one",
            body_ne="ne text",
            body_en="en text",
            is_active=True,
        )
        Announcement.objects.create(
            org=gym.org,
            gym=gym,
            title="Inactive one",
            body_ne="ne text 2",
            body_en="en text 2",
            is_active=False,
        )

    token = signing.dumps({"member_id": member.pk}, salt=PASS_SALT)
    client = APIClient()
    response = client.get(f"/api/v1/m/pass/{token}/announcements")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["title"] == "Active one"
    assert body[0]["body"] == "ne text"  # member.language defaults to "ne"
