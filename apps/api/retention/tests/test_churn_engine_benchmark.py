"""Performance requirement: churn_engine must finish in < 2 minutes for
50,000 members in a single gym (its whole point is one SQL UPDATE per gym,
not a per-row Python loop -- see retention/tasks.py's _CHURN_ENGINE_SQL).
"""

from __future__ import annotations

import time
from datetime import timedelta

import pytest
from django.db import connection
from django.utils import timezone

from core.context import system_context
from gyms.models import Gym, Organization
from members.models import Member
from retention.tasks import churn_engine

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.benchmark]

MEMBER_COUNT = 50_000
TIME_BUDGET_SECONDS = 120


def test_churn_engine_handles_50000_members_within_budget():
    # Test data only (dropped with the rest of the test DB) -- safe to trade
    # commit durability for speed here, unlike in production.
    with connection.cursor() as cursor:
        cursor.execute("SET synchronous_commit = off")

    with system_context():
        org = Organization.objects.create(name="Churn Benchmark Org")
        gym = Gym.objects.create(org=org, code="BENCH1", name="Churn Benchmark Gym")

        now = timezone.now()
        members = [
            Member(
                org=org,
                gym=gym,
                member_code=f"BENCH1-{i:06d}",
                full_name=f"Member {i}",
                phone=f"+977980{i:07d}",
                qr_secret=b"fixture-not-a-real-secret",
                # Spread last_check_in_at so some land normal, some warning,
                # some red_list -- a realistic mixed workload, not a single
                # trivial case the planner could special-case.
                last_check_in_at=now - timedelta(days=i % 40),
            )
            for i in range(MEMBER_COUNT)
        ]
        Member.objects.bulk_create(members, batch_size=2000)

    started = time.monotonic()
    changed = churn_engine()
    elapsed = time.monotonic() - started

    assert elapsed < TIME_BUDGET_SECONDS, (
        f"churn_engine took {elapsed:.1f}s for {MEMBER_COUNT} members"
    )
    assert changed > 0
