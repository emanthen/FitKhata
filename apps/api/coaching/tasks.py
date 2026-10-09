"""Celery Beat: weekly AI coaching reports (FR-7). Sunday 22:00 NPT for
per-client reports, 23:00 for the branch rollup (migrations/0005).

generate_weekly_coaching_reports does only cheap DB reads + enqueue — the
Anthropic HTTP call lives exclusively in generate_client_coaching_report,
a separate task, never inline here. This mirrors retention's
churn_engine/notify_risk_transitions split: notifications' first draft put
a per-member call inline in a batch-iteration task and blew a 50k-member
benchmark from 120s to 468s. Same shape, same reason, applied from the
start this time.
"""

from __future__ import annotations

from datetime import date, timedelta

from celery import shared_task
from django.utils import timezone

from coaching import ai
from coaching.models import ClientProfile
from core.context import system_context, tenant_context
from core.domain.nptime import to_kathmandu
from gyms.models import Gym

GYM_BATCH_SIZE = 200


def _gym_id_batches() -> list[list]:
    with system_context():
        ids = list(Gym.objects.order_by("id").values_list("id", flat=True))
    return [ids[i : i + GYM_BATCH_SIZE] for i in range(0, len(ids), GYM_BATCH_SIZE)]


def _this_week_monday() -> date:
    today = to_kathmandu(timezone.now()).date()
    return today - timedelta(days=today.weekday())


@shared_task
def generate_weekly_coaching_reports() -> int:
    week_start = _this_week_monday()
    enqueued = 0

    for batch in _gym_id_batches():
        for gym_id in batch:
            with tenant_context([str(gym_id)]):
                profile_ids = list(
                    ClientProfile.objects.filter(
                        gym_id=gym_id, consent_health_data=True
                    ).values_list("id", flat=True)
                )
            for profile_id in profile_ids:
                generate_client_coaching_report.delay(str(profile_id), week_start.isoformat())
                enqueued += 1

    return enqueued


@shared_task
def generate_client_coaching_report(profile_id: str, week_start: str) -> None:
    with system_context():
        gym_id = str(ClientProfile.objects.get(pk=profile_id).gym_id)
    with tenant_context([gym_id]):
        profile = ClientProfile.objects.select_related("member", "gym", "diet_plan").get(
            pk=profile_id
        )
        ai.generate_weekly_report(profile, date.fromisoformat(week_start))


@shared_task
def generate_branch_coaching_reports() -> int:
    week_start = _this_week_monday()
    generated = 0

    for batch in _gym_id_batches():
        for gym_id in batch:
            with system_context():
                gym = Gym.objects.get(pk=gym_id)
            with tenant_context([str(gym_id)]):
                ai.generate_branch_report(gym, week_start)
                generated += 1

    return generated
