"""Celery Beat: re-verify payments the gateway's own callback never
confirmed (FR-4.5) — a member closed the tab mid-redirect, a webhook got
dropped, etc. Scheduled every 10 minutes via a data migration registering
a PeriodicTask row (migrations/0007_pending_payment_reverification.py) —
django_celery_beat's DatabaseScheduler (config/settings/base.py) reads
schedules from the DB, so a static CELERY_BEAT_SCHEDULE dict wouldn't be
picked up, same reasoning as attendance/tasks.py's partition job.
"""

from __future__ import annotations

from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from billing.gateways.base import GatewayNotConfigured, GatewayVerificationFailed
from billing.gateways.esewa import EsewaGateway
from billing.gateways.khalti import KhaltiGateway
from billing.models import GatewayCredential, Payment
from billing.services import collect_payment
from core.context import system_context

STALE_AFTER_MINUTES = 15


@shared_task
def reverify_pending_payments() -> int:
    """Returns the count of payments successfully confirmed this run."""
    cutoff = timezone.now() - timedelta(minutes=STALE_AFTER_MINUTES)
    confirmed = 0

    with system_context():
        stale = Payment.objects.filter(
            status=Payment.Status.PENDING,
            channel=Payment.Channel.ONLINE,
            created_at__lt=cutoff,
        ).select_related("gym")

        for payment in stale:
            try:
                if payment.mode == GatewayCredential.Provider.ESEWA:
                    result = EsewaGateway().check_status(
                        payment.gym, f"{payment.amount_npr:.2f}", str(payment.transaction_uuid)
                    )
                elif payment.mode == GatewayCredential.Provider.KHALTI:
                    if not payment.gateway_ref:
                        continue  # never got far enough to have a pidx to look up
                    result = KhaltiGateway().verify(
                        {
                            "pidx": payment.gateway_ref,
                            "gym": payment.gym,
                            "expected_amount_paisa": int(payment.amount_npr * 100),
                        }
                    )
                else:
                    continue  # Fonepay is desk-only, never "pending online" here
            except (GatewayNotConfigured, GatewayVerificationFailed):
                continue

            if result.completed:
                collect_payment(
                    payment, gateway_ref=result.gateway_ref, raw_response=result.raw_response
                )
                confirmed += 1

    return confirmed
