from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from core.context import system_context
from gyms.models import Gym, Organization
from members.models import Member, Plan
from members.services import register_member, sell_membership
from notifications.models import Notification
from retention.models import FreezeRequest, MembershipFreeze
from retention.services import (
    MaxFreezeDaysExceeded,
    apply_individual_freeze,
    approve_freeze_request,
    confirm_bulk_freeze,
    preview_bulk_freeze,
    reject_freeze_request,
    request_freeze,
    revert_freeze_batch,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def gym():
    with system_context():
        org = Organization.objects.create(name="Retention Test Org")
        return Gym.objects.create(org=org, code="RET1", name="Retention Test Gym")


@pytest.fixture
def plan(gym):
    with system_context():
        return Plan.objects.create(
            org=gym.org,
            gym=gym,
            name="Monthly",
            duration_days=30,
            price_npr=Decimal("3000.00"),
            max_freeze_days=15,
        )


@pytest.fixture
def membership(gym, plan):
    with system_context():
        member = register_member(gym, full_name="Ram Shrestha", phone="+9779800000001")
        return sell_membership(member, plan, today=date(2026, 1, 1))


# --- apply_individual_freeze: max_freeze_days enforcement (FR-5.9) ---------


def test_individual_freeze_shifts_expiry_by_frozen_days(membership):
    with system_context():
        freeze = apply_individual_freeze(
            membership, date(2026, 1, 10), date(2026, 1, 19), reason="travel"
        )
        assert freeze.days == 10
        membership.refresh_from_db()
        assert membership.expiry_date == date(2026, 2, 9)  # was Jan 30 + 10


def test_individual_freeze_reaches_notify_for_freeze_applied(membership):
    with system_context():
        apply_individual_freeze(membership, date(2026, 1, 10), date(2026, 1, 12), reason="injury")
        assert Notification.objects.filter(
            member=membership.member, template_key="freeze_applied"
        ).exists()


def test_individual_freeze_sets_member_frozen(membership):
    with system_context():
        apply_individual_freeze(membership, date(2026, 1, 10), date(2026, 1, 12), reason="injury")
        membership.member.refresh_from_db()
        assert membership.member.status == Member.Status.FROZEN


def test_individual_freeze_within_max_days_succeeds(membership):
    with system_context():
        # plan.max_freeze_days == 15; this uses exactly 15.
        freeze = apply_individual_freeze(
            membership, date(2026, 1, 1), date(2026, 1, 15), reason="other"
        )
    assert freeze.days == 15


def test_individual_freeze_exceeding_max_days_is_rejected(membership):
    with system_context():
        with pytest.raises(MaxFreezeDaysExceeded):
            apply_individual_freeze(
                membership, date(2026, 1, 1), date(2026, 1, 16), reason="other"
            )


def test_individual_freeze_accumulates_across_calls(membership):
    with system_context():
        apply_individual_freeze(membership, date(2026, 1, 1), date(2026, 1, 10), reason="travel")
        # 10 used already; 6 more would total 16 > max_freeze_days (15).
        with pytest.raises(MaxFreezeDaysExceeded):
            apply_individual_freeze(
                membership, date(2026, 2, 1), date(2026, 2, 6), reason="travel"
            )


def test_reverted_freeze_days_do_not_count_against_the_cap(membership):
    with system_context():
        freeze = apply_individual_freeze(
            membership, date(2026, 1, 1), date(2026, 1, 10), reason="travel"
        )
        revert_freeze_batch(freeze.batch_id, membership.gym)
        # Now the full 15 days are available again.
        second = apply_individual_freeze(
            membership, date(2026, 2, 1), date(2026, 2, 15), reason="travel"
        )
    assert second.days == 15


# --- Member-initiated freeze requests (FR-8.6) ------------------------------


def test_request_freeze_creates_pending_row_with_no_membership_mutation(membership):
    with system_context():
        before_expiry = membership.expiry_date
        freeze_request = request_freeze(
            membership.member, membership, date(2026, 1, 1), date(2026, 1, 10), "travel"
        )
        membership.refresh_from_db()

    assert freeze_request.status == FreezeRequest.Status.PENDING
    assert membership.expiry_date == before_expiry


def test_approve_freeze_request_applies_freeze_and_flips_status(membership):
    with system_context():
        freeze_request = request_freeze(
            membership.member, membership, date(2026, 1, 1), date(2026, 1, 10), "travel"
        )
        approve_freeze_request(freeze_request, actor=None)
        membership.refresh_from_db()
        has_freeze = MembershipFreeze.objects.filter(membership=membership).exists()

    assert freeze_request.status == FreezeRequest.Status.APPROVED
    assert freeze_request.reviewed_at is not None
    assert membership.expiry_date == date(2026, 2, 9)  # Jan 30 + 10 days
    assert has_freeze


def test_reject_freeze_request_only_flips_status(membership):
    with system_context():
        before_expiry = membership.expiry_date
        freeze_request = request_freeze(
            membership.member, membership, date(2026, 1, 1), date(2026, 1, 10), "travel"
        )
        reject_freeze_request(freeze_request, actor=None)
        membership.refresh_from_db()

    assert freeze_request.status == FreezeRequest.Status.REJECTED
    assert membership.expiry_date == before_expiry


def test_approve_freeze_request_past_max_days_raises_and_stays_pending(membership):
    with system_context():
        freeze_request = request_freeze(
            membership.member, membership, date(2026, 1, 1), date(2026, 1, 16), "travel"
        )
        with pytest.raises(MaxFreezeDaysExceeded):
            approve_freeze_request(freeze_request, actor=None)
        freeze_request.refresh_from_db()

    assert freeze_request.status == FreezeRequest.Status.PENDING


# --- bulk freeze / revert round-trip (FR-5.8) -------------------------------


def test_bulk_freeze_preview_does_not_write_anything(membership):
    with system_context():
        rows = preview_bulk_freeze(membership.gym, date(2026, 10, 1), date(2026, 10, 10))
    assert len(rows) == 1
    assert rows[0].previous_expiry == date(2026, 1, 30)
    assert rows[0].new_expiry == date(2026, 2, 9)
    assert MembershipFreeze.objects.count() == 0


def test_bulk_freeze_confirm_then_revert_restores_exact_previous_expiry(membership):
    original_expiry = membership.expiry_date
    with system_context():
        batch_id = confirm_bulk_freeze(
            membership.gym, date(2026, 10, 1), date(2026, 10, 10), reason="dashain"
        )
        membership.refresh_from_db()
        assert membership.expiry_date == date(2026, 2, 9)
        membership.member.refresh_from_db()
        assert membership.member.status == Member.Status.FROZEN

        reverted_count = revert_freeze_batch(batch_id, membership.gym)

        assert reverted_count == 1
        membership.refresh_from_db()
        assert membership.expiry_date == original_expiry
        membership.member.refresh_from_db()
        assert membership.member.status == Member.Status.ACTIVE


def test_bulk_freeze_skips_memberships_that_would_exceed_their_cap(gym, plan):
    with system_context():
        member = register_member(gym, full_name="Hari Tamang", phone="+9779800000002")
        tight_membership = sell_membership(member, plan, today=date(2026, 1, 1))
        apply_individual_freeze(
            tight_membership, date(2026, 1, 1), date(2026, 1, 10), reason="travel"
        )  # uses 10 of 15

        # +10 more would total 20 > max_freeze_days (15) -- skipped.
        confirm_bulk_freeze(gym, date(2026, 6, 1), date(2026, 6, 10), reason="dashain")
        tight_membership.refresh_from_db()

    # Skipped: expiry is whatever it became after the first individual
    # freeze only (Jan 30 + 10 = Feb 9), the bulk freeze did not touch it.
    assert tight_membership.expiry_date == date(2026, 2, 9)
