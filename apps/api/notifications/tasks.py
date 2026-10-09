"""One Celery task per channel (FR-6.5) — different providers have
different real-world rate limits, so each gets its own `rate_limit` rather
than a generic dispatcher that would just be a pass-through. Each task's
entire job is "call the provider, then let handle_delivery_outcome() decide
what happens next" — the retry/fallback/dead-letter decision itself is
already fully tested in notifications/domain/tests/test_retry.py and
notifications/tests/test_services.py, so there's nothing left to test here
beyond "does this task call the right provider function".

Beat schedule for send_birthday_notifications is registered via
migrations/0004_beat_schedule.py — same django_celery_beat DatabaseScheduler
reasoning as billing/migrations/0007_... and retention/migrations/0003_....
"""

from __future__ import annotations

from celery import shared_task
from django.utils import timezone

from accounts.sms import get_sms_provider
from core.context import system_context, tenant_context
from core.domain.nptime import to_kathmandu
from gyms.models import Gym
from members.models import Member
from notifications.domain.retry import ProviderPermanentError
from notifications.models import Notification, PushSubscription
from notifications.providers import email as email_provider
from notifications.providers import push as push_provider
from notifications.providers import whatsapp as whatsapp_provider
from notifications.services import handle_delivery_outcome, notify

GYM_BATCH_SIZE = 200


def _gym_id_batches() -> list[list]:
    with system_context():
        ids = list(Gym.objects.order_by("id").values_list("id", flat=True))
    return [ids[i : i + GYM_BATCH_SIZE] for i in range(0, len(ids), GYM_BATCH_SIZE)]


@shared_task(bind=True, max_retries=5, rate_limit="60/m")
def send_sms_notification(self, notification_id):
    notification = Notification.objects.select_related("member").get(pk=notification_id)
    try:
        get_sms_provider().send(notification.member.phone, notification.payload["body"])
    except Exception as exc:  # noqa: BLE001 — classified by handle_delivery_outcome, not here
        decision = handle_delivery_outcome(notification, success=False, exc=exc)
        if decision.action == "retry":
            raise self.retry(exc=exc, countdown=decision.retry_countdown) from exc
        return
    handle_delivery_outcome(notification, success=True)


@shared_task(bind=True, max_retries=5, rate_limit="250/m")
def send_whatsapp_notification(self, notification_id):
    notification = Notification.objects.select_related("member").get(pk=notification_id)
    try:
        provider_ref = whatsapp_provider.send(
            notification.member.phone,
            notification.payload.get("whatsapp_template_name", ""),
            notification.language,
            [],
        )
    except Exception as exc:  # noqa: BLE001
        decision = handle_delivery_outcome(notification, success=False, exc=exc)
        if decision.action == "retry":
            raise self.retry(exc=exc, countdown=decision.retry_countdown) from exc
        return
    notification.provider_ref = provider_ref
    notification.save(update_fields=["provider_ref"])
    handle_delivery_outcome(notification, success=True)


@shared_task(bind=True, max_retries=5, rate_limit="500/m")
def send_push_notification(self, notification_id):
    notification = Notification.objects.select_related("member").get(pk=notification_id)
    subscription = PushSubscription.objects.filter(member=notification.member).first()
    if subscription is None:
        # No subscription is a permanent condition for this notification —
        # retrying won't make one appear, so this falls back immediately
        # rather than burning retries, same as push_provider.send()'s own
        # 404/410 handling for a subscription that existed but went stale.
        handle_delivery_outcome(
            notification,
            success=False,
            exc=ProviderPermanentError("No push subscription for member"),
        )
        return
    try:
        push_provider.send(subscription, title="FitKhata", body=notification.payload["body"])
    except Exception as exc:  # noqa: BLE001
        decision = handle_delivery_outcome(notification, success=False, exc=exc)
        if decision.action == "retry":
            raise self.retry(exc=exc, countdown=decision.retry_countdown) from exc
        return
    handle_delivery_outcome(notification, success=True)


@shared_task(bind=True, max_retries=5, rate_limit="100/m")
def send_email_notification(self, notification_id):
    notification = Notification.objects.select_related("member").get(pk=notification_id)
    try:
        email_provider.send(
            notification.member.email, subject="FitKhata", body=notification.payload["body"]
        )
    except Exception as exc:  # noqa: BLE001
        decision = handle_delivery_outcome(notification, success=False, exc=exc)
        if decision.action == "retry":
            raise self.retry(exc=exc, countdown=decision.retry_countdown) from exc
        return
    handle_delivery_outcome(notification, success=True)


@shared_task
def send_birthday_notifications() -> int:
    """08:00 Asia/Kathmandu, after quiet hours end — same batching shape as
    retention/tasks.py's nightly jobs.
    """
    today = to_kathmandu(timezone.now()).date()
    sent_total = 0

    for batch in _gym_id_batches():
        for gym_id in batch:
            with tenant_context([str(gym_id)]):
                members = Member.objects.filter(
                    gym_id=gym_id, dob__month=today.month, dob__day=today.day
                )
                for member in members:
                    if notify(member, "birthday", {"name": member.full_name}) is not None:
                        sent_total += 1

    return sent_total
