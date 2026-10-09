"""Real concurrent DB contention (not just sequential calls) — needs its
own connections per thread to actually exercise select_for_update's
locking, hence transaction=True (plain django_db wraps everything in one
outer transaction only the test's own thread sees).
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from decimal import Decimal

import pytest
from django.db import connection

from billing.services import InvoiceLineInput, create_draft_invoice
from core.context import system_context
from gyms.models import Gym, Organization
from members.models import Member

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.benchmark]

CONCURRENT_INVOICES = 50


def _issue_one_invoice(gym_id, member_id) -> str:
    """Runs in its own thread, hence its own DB connection — re-fetches
    gym/member by id rather than sharing the fixture's ORM instances
    across threads (Django model instances aren't meant to cross threads).
    """
    try:
        with system_context():
            gym = Gym.objects.get(pk=gym_id)
            member = Member.objects.get(pk=member_id)
            invoice = create_draft_invoice(
                gym,
                member,
                [InvoiceLineInput("Walk-in session", 1, Decimal("500.00"), Decimal("500.00"))],
                Decimal("500.00"),
                Decimal("0.00"),
                Decimal("500.00"),
                today=date(2026, 1, 1),
            )
            return invoice.number
    finally:
        connection.close()  # each thread's own connection, don't leak it


def test_fifty_concurrent_invoices_are_gapless_and_unique():
    with system_context():
        org = Organization.objects.create(name="Concurrency Test Org")
        gym = Gym.objects.create(org=org, code="CONC1", name="Concurrency Test Gym")
        member = Member.objects.create(
            org=org,
            gym=gym,
            member_code="CONC1-0001",
            full_name="Test Member",
            phone="+9779800000001",
            qr_secret=b"fixture-not-a-real-secret",
        )
        gym_id, member_id = gym.pk, member.pk

    with ThreadPoolExecutor(max_workers=CONCURRENT_INVOICES) as pool:
        futures = [
            pool.submit(_issue_one_invoice, gym_id, member_id) for _ in range(CONCURRENT_INVOICES)
        ]
        numbers = [future.result() for future in as_completed(futures)]

    assert len(numbers) == CONCURRENT_INVOICES
    assert len(set(numbers)) == CONCURRENT_INVOICES  # no two threads got the same number

    sequence_numbers = sorted(int(n.split("-")[1]) for n in numbers)
    assert sequence_numbers == list(range(1, CONCURRENT_INVOICES + 1))  # gapless, 1..50
