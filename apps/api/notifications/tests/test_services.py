from __future__ import annotations

from decimal import Decimal

import pytest

from core.context import system_context
from gyms.models import Gym, Organization
from members.models import Member
from members.services import register_member
from notifications.domain.retry import ProviderPermanentError
from notifications.models import Notification, SmsWallet, SmsWalletTx
from notifications.services import (
    estimate_broadcast,
    handle_delivery_outcome,
    notify,
    send_broadcast,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def gym():
    with system_context():
        org = Organization.objects.create(name="Notifications Test Org")
        return Gym.objects.create(org=org, code="NTF1", name="Notifications Test Gym")


@pytest.fixture
def funded_gym(gym):
    with system_context():
        SmsWallet.objects.create(org=gym.org, balance_npr=Decimal("1000.00"))
    return gym


@pytest.fixture
def member(funded_gym):
    # Deliberately Member.objects.create(), not register_member() — the
    # latter's own "welcome" notify() call would debit the wallet before
    # these tests get a chance to, contaminating the balance assertions.
    with system_context():
        return Member.objects.create(
            org=funded_gym.org,
            gym=funded_gym,
            member_code="NTF1-0001",
            full_name="Ram Shrestha",
            phone="+9779800000001",
            qr_secret=b"fixture-not-a-real-secret",
        )


# --- Opt-out respected -------------------------------------------------------


def test_notify_returns_none_and_creates_nothing_for_an_opted_out_member(funded_gym):
    with system_context():
        member = register_member(
            funded_gym,
            full_name="Opted Out Member",
            phone="+9779800000099",
            notifications_opt_out=True,
        )
        # register_member() itself already calls notify() for "welcome" —
        # clear that row so this test only asserts on the call under test.
        Notification.objects.filter(member=member).delete()

        result = notify(member, "payment_receipt", {"name": member.full_name})

    assert result is None
    assert Notification.objects.filter(member=member).count() == 0


def test_notify_returns_none_when_the_gym_has_toggled_the_event_off(funded_gym):
    with system_context():
        funded_gym.settings = {**funded_gym.settings, "notification_events": {"winback": False}}
        funded_gym.save(update_fields=["settings"])
        member = register_member(funded_gym, full_name="Toggle Test", phone="+9779800000098")
        Notification.objects.filter(member=member).delete()

        result = notify(member, "winback", {"name": member.full_name})

    assert result is None
    assert Notification.objects.filter(member=member).count() == 0


# --- Insufficient wallet balance skips sms -----------------------------------


def test_notify_with_no_viable_channel_creates_a_terminal_failed_row(gym):
    """`gym` (not `funded_gym`) has no SmsWallet at all, no push subscription,
    no WhatsApp token configured in test settings — nothing is viable.
    """
    with system_context():
        member = register_member(gym, full_name="No Channel", phone="+9779800000002")
        Notification.objects.filter(member=member).delete()

        result = notify(member, "payment_receipt", {"name": member.full_name})

    assert result is not None
    assert result.status == Notification.Status.FAILED
    assert result.template_key == "payment_receipt"


# --- Call-site wiring: register_member -> welcome ----------------------------


def test_register_member_reaches_notify_for_welcome(funded_gym):
    with system_context():
        member = register_member(funded_gym, full_name="Hari Tamang", phone="+9779800000003")
        assert Notification.objects.filter(member=member, template_key="welcome").exists()


# --- NPR cost math + wallet debit --------------------------------------------


def test_sms_delivery_debits_the_wallet_by_sms_cost(funded_gym, member, settings):
    with system_context():
        notification = Notification.objects.create(
            org=member.org,
            gym=member.gym,
            member=member,
            channel="sms",
            template_key="payment_receipt",
            language=member.language,
            payload={"body": "test"},
        )
        handle_delivery_outcome(notification, success=True)

        wallet = SmsWallet.objects.get(org=funded_gym.org)
        tx = SmsWalletTx.objects.get(notification=notification)

    assert wallet.balance_npr == Decimal("1000.00") - settings.SMS_COST_NPR
    assert tx.amount_npr == -settings.SMS_COST_NPR
    assert notification.cost_npr == settings.SMS_COST_NPR


def test_estimate_broadcast_sms_cost_matches_recipient_count(funded_gym, settings):
    with system_context():
        for i in range(3):
            bulk_member = register_member(
                funded_gym, full_name=f"Bulk {i}", phone=f"+97798000001{i}"
            )
            bulk_member.status = Member.Status.EXPIRED
            bulk_member.save(update_fields=["status"])

        count, cost = estimate_broadcast(funded_gym, "expired", "", "sms")

    assert count == 3
    assert cost == Decimal(3) * settings.SMS_COST_NPR


# --- Provider failure falls back to next channel -----------------------------


def test_permanent_failure_on_whatsapp_falls_back_to_sms(funded_gym, member):
    with system_context():
        funded_gym.settings = {
            **funded_gym.settings,
            "notification_channel_order": ["whatsapp", "sms"],
        }
        funded_gym.save(update_fields=["settings"])

        notification = Notification.objects.create(
            org=member.org,
            gym=member.gym,
            member=member,
            channel="whatsapp",
            template_key="payment_receipt",
            language=member.language,
            payload={"body": "test", "context": {}},
        )
        decision = handle_delivery_outcome(
            notification, success=False, exc=ProviderPermanentError("bad template")
        )

        fallback = Notification.objects.get(fallback_of=notification)
        notification.refresh_from_db()

    assert decision.action == "fallback"
    assert decision.next_channel == "sms"
    assert fallback.channel == "sms"
    assert fallback.member_id == member.pk
    assert notification.status == Notification.Status.FAILED


def test_transient_failure_retries_before_falling_back(member):
    with system_context():
        notification = Notification.objects.create(
            org=member.org,
            gym=member.gym,
            member=member,
            channel="whatsapp",
            template_key="payment_receipt",
            language=member.language,
            payload={"body": "test", "context": {}},
        )
        decision = handle_delivery_outcome(notification, success=False, exc=Exception("timeout"))
        no_fallback_created = Notification.objects.filter(fallback_of=notification).count() == 0

    assert decision.action == "retry"
    assert no_fallback_created


def test_dead_letter_when_no_channel_is_left_to_fall_back_to(funded_gym, member):
    with system_context():
        funded_gym.settings = {**funded_gym.settings, "notification_channel_order": ["whatsapp"]}
        funded_gym.save(update_fields=["settings"])

        notification = Notification.objects.create(
            org=member.org,
            gym=member.gym,
            member=member,
            channel="whatsapp",
            template_key="payment_receipt",
            language=member.language,
            payload={"body": "test", "context": {}},
        )
        decision = handle_delivery_outcome(
            notification, success=False, exc=ProviderPermanentError("bad template")
        )
        no_fallback_created = Notification.objects.filter(fallback_of=notification).count() == 0

    assert decision.action == "dead_letter"
    assert no_fallback_created


# --- Broadcast segments -------------------------------------------------------


def test_send_broadcast_only_reaches_viable_members(funded_gym):
    with system_context():
        with_phone = register_member(funded_gym, full_name="Has Phone", phone="+9779800000010")
        with_phone.status = Member.Status.EXPIRED
        with_phone.save(update_fields=["status"])
        Notification.objects.filter(member=with_phone).delete()

        broadcast = send_broadcast(
            funded_gym, "expired", "", "sms", body_ne="ne body", body_en="en body"
        )
        reached = Notification.objects.filter(member=with_phone, template_key="").exists()

    assert broadcast.recipient_count == 1
    assert reached
