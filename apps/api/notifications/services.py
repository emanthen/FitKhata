"""notify() (FR-6.3), its delivery-outcome handling (FR-6.5/6.6), and
broadcast-to-segment (FR-6.4). Rule 9: views stay thin, this is where the
actual logic lives — the pure decision-making itself lives one layer down
in notifications/domain/, this module is just the DB-facing glue around it.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from core.services import audit
from members.models import Member, Membership
from notifications.domain.cost import broadcast_cost_npr
from notifications.domain.quiet_hours import next_send_time
from notifications.domain.render import render
from notifications.domain.retry import (
    DeliveryDecision,
    ProviderPermanentError,
    decide_delivery_outcome,
)
from notifications.models import (
    Broadcast,
    Notification,
    PushSubscription,
    SmsWallet,
    SmsWalletTx,
    Template,
)

DEFAULT_CHANNEL_ORDER = ["push", "whatsapp", "sms"]


def resolve_template(org: Any, key: str, channel: str, language: str) -> Template | None:
    """An org-specific row (if the template editor ever created one) beats
    the platform default (org=NULL) — same "specific beats broad default"
    shape as billing.gateways.base.resolve_credential's live/sandbox fallback.
    """
    return (
        Template.objects.filter(
            org=org, key=key, channel=channel, language=language, is_active=True
        ).first()
        or Template.objects.filter(
            org=None, key=key, channel=channel, language=language, is_active=True
        ).first()
    )


def _wallet_balance_sufficient(org: Any) -> bool:
    wallet = SmsWallet.objects.filter(org=org).first()
    balance = wallet.balance_npr if wallet else Decimal("0")
    return balance >= settings.SMS_COST_NPR


def _channel_viable(channel: str, member: Member, org: Any) -> bool:
    if channel == "push":
        return PushSubscription.objects.filter(member=member).exists()
    if channel == "whatsapp":
        return bool(member.phone) and bool(settings.WHATSAPP_CLOUD_API_TOKEN)
    if channel == "sms":
        return bool(member.phone) and _wallet_balance_sufficient(org)
    if channel == "email":
        return bool(member.email)
    return False


def _channel_order(gym: Any) -> list[str]:
    return gym.settings.get("notification_channel_order", DEFAULT_CHANNEL_ORDER)


def _viable_channels(gym: Any, member: Member) -> list[str]:
    return [c for c in _channel_order(gym) if _channel_viable(c, member, gym.org)]


def _payload_for(
    org: Any, event: str, channel: str, language: str, context: dict[str, Any]
) -> dict[str, Any]:
    template = resolve_template(org, event, channel, language)
    body = render(template.body if template else "", context)
    payload: dict[str, Any] = {"body": body, "context": context}
    if channel == "whatsapp" and template and template.whatsapp_template_name:
        payload["whatsapp_template_name"] = template.whatsapp_template_name
    return payload


def notify(
    member: Member, event: str, context: dict[str, Any], actor: Any = None
) -> Notification | None:
    """Returns None if the gym has this event toggled off, or the member has
    opted out of notifications entirely — in both cases no row is created at
    all, since there's nothing to show in a delivery log for a send that was
    never attempted. Returns a terminal failed Notification if the event/
    opt-out checks pass but no channel is actually usable for this member
    (diagnostic value for the delivery log), otherwise creates a queued
    Notification and enqueues the matching per-channel Celery task.
    """
    gym = member.gym
    events_enabled = gym.settings.get("notification_events", {})
    if events_enabled.get(event, True) is False:
        return None
    if member.notifications_opt_out:
        return None

    viable = _viable_channels(gym, member)
    if not viable:
        order = _channel_order(gym)
        return Notification.objects.create(
            org=gym.org,
            gym=gym,
            member=member,
            channel=order[0] if order else "sms",
            template_key=event,
            language=member.language,
            status=Notification.Status.FAILED,
            error="No viable notification channel for this member.",
        )

    channel = viable[0]
    notification = Notification.objects.create(
        org=gym.org,
        gym=gym,
        member=member,
        channel=channel,
        template_key=event,
        language=member.language,
        payload=_payload_for(gym.org, event, channel, member.language, context),
    )
    _enqueue(notification)
    return notification


def _enqueue(notification: Notification) -> None:
    # Lazy import: tasks.py imports handle_delivery_outcome from this module,
    # so importing tasks.py back at module scope here would be circular —
    # same shape as billing/services.py's lazy import of members.services.
    from notifications.tasks import (
        send_email_notification,
        send_push_notification,
        send_sms_notification,
        send_whatsapp_notification,
    )

    task = {
        "sms": send_sms_notification,
        "whatsapp": send_whatsapp_notification,
        "push": send_push_notification,
        "email": send_email_notification,
    }[notification.channel]

    now = timezone.now()
    send_at = next_send_time(now)
    if send_at > now:
        task.apply_async(args=[notification.pk], eta=send_at)
    else:
        task.delay(notification.pk)


def _debit_sms_wallet(org: Any, notification: Notification) -> None:
    with transaction.atomic():
        wallet, _ = SmsWallet.objects.select_for_update().get_or_create(org=org)
        wallet.balance_npr -= settings.SMS_COST_NPR
        wallet.save(update_fields=["balance_npr"])
        SmsWalletTx.objects.create(
            wallet=wallet,
            amount_npr=-settings.SMS_COST_NPR,
            reason=SmsWalletTx.Reason.DEBIT,
            notification=notification,
        )
    notification.cost_npr = settings.SMS_COST_NPR
    notification.save(update_fields=["cost_npr"])


def _already_tried_channels(notification: Notification) -> set[str]:
    tried = {notification.channel}
    cursor: Notification | None = notification
    while cursor is not None and cursor.fallback_of_id:
        cursor = cursor.fallback_of
        if cursor is not None:
            tried.add(cursor.channel)
    return tried


def handle_delivery_outcome(
    notification: Notification, success: bool, exc: Exception | None = None
) -> DeliveryDecision:
    """The Celery task's only real logic: call the provider, then call this.
    `exc` classification is purely isinstance(exc, ProviderPermanentError) —
    anything else (including no exception info at all) is treated as
    transient, which is the conservative choice (retry rather than give up).
    """
    notification.attempt_count += 1
    transient = not isinstance(exc, ProviderPermanentError)

    gym = notification.gym
    member = notification.member
    tried = _already_tried_channels(notification)
    fallback_channel = next(
        (c for c in _channel_order(gym) if c not in tried and _channel_viable(c, member, gym.org)),
        None,
    )

    decision = decide_delivery_outcome(
        attempt_count=notification.attempt_count,
        success=success,
        transient=transient,
        fallback_channel=fallback_channel,
    )

    if decision.action == "delivered":
        notification.status = Notification.Status.SENT
        notification.sent_at = timezone.now()
        notification.save(update_fields=["status", "sent_at", "attempt_count"])
        if notification.channel == "sms":
            _debit_sms_wallet(gym.org, notification)
        return decision

    notification.error = str(exc) if exc else ""

    if decision.action == "retry":
        notification.save(update_fields=["attempt_count", "error"])
        return decision

    notification.status = Notification.Status.FAILED
    notification.save(update_fields=["status", "attempt_count", "error"])

    if decision.action == "fallback":
        assert decision.next_channel is not None
        fallback_notification = Notification.objects.create(
            org=gym.org,
            gym=gym,
            member=member,
            channel=decision.next_channel,
            template_key=notification.template_key,
            language=notification.language,
            payload=_payload_for(
                gym.org,
                notification.template_key,
                decision.next_channel,
                notification.language,
                notification.payload.get("context", {}),
            ),
            fallback_of=notification,
        )
        _enqueue(fallback_notification)

    return decision


# --- Broadcast (FR-6.4) ------------------------------------------------------


def _segment_members(gym: Any, segment: str, value: str):
    qs = Member.objects.filter(gym=gym, notifications_opt_out=False)
    if segment == Broadcast.Segment.EXPIRED:
        return qs.filter(status=Member.Status.EXPIRED)
    if segment == Broadcast.Segment.RED_LIST:
        return qs.filter(risk_state=Member.RiskState.RED_LIST)
    if segment == Broadcast.Segment.PLAN:
        return qs.filter(
            memberships__plan_id=value, memberships__status=Membership.Status.ACTIVE
        ).distinct()
    if segment == Broadcast.Segment.GENDER:
        return qs.filter(gender=value)
    if segment == Broadcast.Segment.TAG:
        return qs.filter(tags__contains=[value])
    return qs.none()


def estimate_broadcast(
    gym: Any, segment: str, segment_value: str, channel: str
) -> tuple[int, Decimal]:
    count = _segment_members(gym, segment, segment_value).count()
    return count, broadcast_cost_npr(count, channel, settings.SMS_COST_NPR)


def send_broadcast(
    gym: Any,
    segment: str,
    segment_value: str,
    channel: str,
    body_ne: str,
    body_en: str,
    actor: Any = None,
) -> Broadcast:
    """Create == send (no draft state) — the composer already ran
    estimate_broadcast() for its preview before this is ever called.
    """
    members = list(_segment_members(gym, segment, segment_value))
    cost = broadcast_cost_npr(len(members), channel, settings.SMS_COST_NPR)
    broadcast = Broadcast.objects.create(
        org=gym.org,
        gym=gym,
        segment=segment,
        segment_value=segment_value,
        channel=channel,
        body_ne=body_ne,
        body_en=body_en,
        recipient_count=len(members),
        cost_npr=cost,
        created_by=actor,
        sent_at=timezone.now(),
    )
    for member in members:
        if not _channel_viable(channel, member, gym.org):
            continue
        body = body_ne if member.language == Member.Language.NEPALI else body_en
        notification = Notification.objects.create(
            org=gym.org,
            gym=gym,
            member=member,
            channel=channel,
            template_key="",
            language=member.language,
            payload={"body": body, "context": {}},
        )
        _enqueue(notification)
    audit(
        broadcast,
        "create",
        after={"segment": segment, "channel": channel, "recipient_count": len(members)},
        actor=actor,
    )
    return broadcast
