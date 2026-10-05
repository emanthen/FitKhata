"""FR-2.12: trigram search over 10,000 members must respond in < 300ms.
Seeded once per module via bulk_create (not register_member — that's
single-row-at-a-time by design, far too slow for 10k rows) using
pytest-django's documented pattern for an expensive module-scoped fixture:
django_db_blocker.unblock() writes directly, outside any per-test
transaction that would otherwise roll it back.
"""

from __future__ import annotations

import os
import random
import time

import pytest
from rest_framework.test import APIClient

from accounts.models import StaffRole, User
from accounts.tokens import issue_tokens_for_user
from core.context import system_context
from gyms.models import Gym, Organization
from members.models import Member

pytestmark = pytest.mark.benchmark

FIRST_NAMES = [
    "Ram", "Sita", "Hari", "Gita", "Shyam", "Radha", "Suresh", "Anita",
    "Prakash", "Sunita", "Bishnu", "Kamala", "Dipak", "Sarita", "Rajesh",
]
LAST_NAMES = [
    "Shrestha", "Gurung", "Thapa", "Rai", "Magar", "Tamang", "Lama",
    "Bastola", "Khadka", "Adhikari",
]


@pytest.fixture(scope="module")
def search_dataset(django_db_blocker):
    with django_db_blocker.unblock():
        with system_context():
            # Defensive, not just belt-and-suspenders: this fixture commits
            # directly (outside pytest-django's per-test rollback) so a
            # previous run that didn't reach its own teardown (e.g. the
            # process was killed, or an assertion failure interacted badly
            # with module-fixture finalization) can leave this org behind
            # and collide on the next run's unique phone/org name.
            Organization.objects.filter(name="Search Benchmark Org").delete()
            User.objects.filter(phone="+9774000000001").delete()
            org = Organization.objects.create(name="Search Benchmark Org")
            gym = Gym.objects.create(org=org, code="SRCH1", name="Search Benchmark Gym")
            owner = User.objects.create_user(phone="+9774000000001", password="x")
            StaffRole.objects.create(user=owner, org=org, gym=gym, role=StaffRole.Role.OWNER)

            rng = random.Random(42)
            members = [
                Member(
                    org=org,
                    gym=gym,
                    member_code=f"SRCH1-{i:05d}",
                    full_name=f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}",
                    phone=f"+97798{i:08d}",
                    qr_secret=os.urandom(32),
                )
                for i in range(10_000)
            ]
            # One findable-by-name needle, since random names may collide.
            members.append(
                Member(
                    org=org,
                    gym=gym,
                    member_code="SRCH1-NEEDLE",
                    full_name="Zzyzxoth Uniquename",
                    phone="+9779999999999",
                    qr_secret=os.urandom(32),
                )
            )
            Member.objects.bulk_create(members, batch_size=1000)

        yield org, gym, owner

        with system_context():
            org.delete()


def test_search_10k_members_under_300ms(search_dataset):
    _org, gym, owner = search_dataset
    tokens = issue_tokens_for_user(owner)
    client = APIClient()
    client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {tokens['access']}", HTTP_X_GYM_ID=str(gym.pk)
    )

    # One untimed warm-up request first: the acceptance target is steady-
    # state latency, not this test process's first-ever request, which
    # pays one-time costs (URL resolver caching, serializer/permission
    # class imports, DB connection setup) no warmed production server pays
    # on every request either.
    client.get("/api/v1/members/", {"q": "Zzyzxoth"})

    started = time.perf_counter()
    response = client.get("/api/v1/members/", {"q": "Zzyzxoth"})
    elapsed_ms = (time.perf_counter() - started) * 1000

    assert response.status_code == 200
    names = [m["full_name"] for m in response.json()]
    assert "Zzyzxoth Uniquename" in names
    assert elapsed_ms < 300, f"search took {elapsed_ms:.1f}ms, acceptance is <300ms"
