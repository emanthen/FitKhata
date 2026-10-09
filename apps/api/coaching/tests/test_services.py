from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, date, datetime
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.db import connection

from coaching.models import ClassBooking, ClassSchedule, CoachingReport
from coaching.services import (
    AlreadyBooked,
    approve_coaching_report,
    book_class,
    cancel_booking,
    create_client_profile,
    record_measurement,
)
from core.context import system_context
from gyms.models import Gym, Organization
from members.services import register_member

pytestmark = pytest.mark.django_db


@pytest.fixture
def gym():
    with system_context():
        org = Organization.objects.create(name="Coaching Services Test Org")
        return Gym.objects.create(org=org, code="CST1", name="Coaching Services Test Gym")


@pytest.fixture
def schedule(gym):
    with system_context():
        return ClassSchedule.objects.create(
            org=gym.org,
            gym=gym,
            name="Morning Yoga",
            trainer=None,
            starts_at=datetime(2026, 10, 10, 7, 0, tzinfo=UTC),
            capacity=1,
        )


# --- book_class / cancel_booking: waitlist auto-promote (FR-7.10) -----------


def test_book_class_fills_capacity_then_waitlists(gym, schedule):
    with system_context():
        member_a = register_member(gym, full_name="Member A", phone="+9779800000001")
        member_b = register_member(gym, full_name="Member B", phone="+9779800000002")

        booking_a = book_class(schedule, member_a)
        booking_b = book_class(schedule, member_b)

    assert booking_a.status == ClassBooking.Status.BOOKED
    assert booking_b.status == ClassBooking.Status.WAITLIST


def test_book_class_notifies_exactly_once_when_booked(gym, schedule):
    with system_context():
        member = register_member(gym, full_name="Member A", phone="+9779800000005")
        with patch("coaching.services.notify") as mock_notify:
            booking = book_class(schedule, member)

    assert booking.status == ClassBooking.Status.BOOKED
    mock_notify.assert_called_once()
    assert mock_notify.call_args.args[1] == "class_booked"


def test_book_class_does_not_notify_when_waitlisted(gym, schedule):
    with system_context():
        member_a = register_member(gym, full_name="Member A", phone="+9779800000006")
        member_b = register_member(gym, full_name="Member B", phone="+9779800000007")
        book_class(schedule, member_a)
        with patch("coaching.services.notify") as mock_notify:
            waitlisted = book_class(schedule, member_b)

    assert waitlisted.status == ClassBooking.Status.WAITLIST
    mock_notify.assert_not_called()


def test_cancelling_a_booked_slot_promotes_the_oldest_waitlisted_member(gym, schedule):
    with system_context():
        member_a = register_member(gym, full_name="Member A", phone="+9779800000003")
        member_b = register_member(gym, full_name="Member B", phone="+9779800000004")

        booking_a = book_class(schedule, member_a)
        booking_b = book_class(schedule, member_b)
        assert booking_b.status == ClassBooking.Status.WAITLIST

        with patch("coaching.services.notify") as mock_notify:
            cancel_booking(booking_a)

        booking_b.refresh_from_db()

    assert booking_b.status == ClassBooking.Status.BOOKED
    mock_notify.assert_called_once()
    assert mock_notify.call_args.args[1] == "class_booking_promoted"


def test_cancelling_a_waitlisted_booking_promotes_nobody(gym, schedule):
    with system_context():
        member_a = register_member(gym, full_name="Member A", phone="+9779800000005")
        member_b = register_member(gym, full_name="Member B", phone="+9779800000006")

        book_class(schedule, member_a)
        booking_b = book_class(schedule, member_b)
        assert booking_b.status == ClassBooking.Status.WAITLIST

        with patch("coaching.services.notify") as mock_notify:
            cancel_booking(booking_b)

    mock_notify.assert_not_called()


def test_booking_twice_without_cancelling_raises(gym, schedule):
    with system_context():
        member = register_member(gym, full_name="Repeat Booker", phone="+9779800000007")
        book_class(schedule, member)
        with pytest.raises(AlreadyBooked):
            book_class(schedule, member)


# --- Real concurrency: two cancels, one waitlisted member, one promotion ----


@pytest.mark.django_db(transaction=True)
@pytest.mark.benchmark
def test_concurrent_cancels_promote_exactly_one_waitlisted_member():
    with system_context():
        org = Organization.objects.create(name="Coaching Concurrency Org")
        gym = Gym.objects.create(org=org, code="CCX1", name="Coaching Concurrency Gym")
        schedule = ClassSchedule.objects.create(
            org=org,
            gym=gym,
            name="Full Class",
            starts_at=datetime(2026, 10, 10, 7, 0, tzinfo=UTC),
            capacity=2,
        )
        member_a = register_member(gym, full_name="A", phone="+9779800000010")
        member_b = register_member(gym, full_name="B", phone="+9779800000011")
        member_c = register_member(gym, full_name="C", phone="+9779800000012")

        booking_a = book_class(schedule, member_a)
        booking_b = book_class(schedule, member_b)
        waitlisted = book_class(schedule, member_c)
        assert booking_a.status == booking_b.status == ClassBooking.Status.BOOKED
        assert waitlisted.status == ClassBooking.Status.WAITLIST

        booking_a_id, booking_b_id = booking_a.pk, booking_b.pk

    def _cancel(booking_id) -> None:
        try:
            with system_context():
                booking = ClassBooking.objects.get(pk=booking_id)
                with patch("coaching.services.notify"):
                    cancel_booking(booking)
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(_cancel, booking_a_id), pool.submit(_cancel, booking_b_id)]
        for future in as_completed(futures):
            future.result()

    with system_context():
        booked_count = ClassBooking.objects.filter(
            class_schedule=schedule, status=ClassBooking.Status.BOOKED
        ).count()
        cancelled_count = ClassBooking.objects.filter(
            class_schedule=schedule, status=ClassBooking.Status.CANCELLED
        ).count()

    # Exactly one promotion: the single waitlisted member fills one of the
    # two freed slots; the other stays empty (no second waitlisted member).
    assert booked_count == 1
    assert cancelled_count == 2


# --- record_measurement -------------------------------------------------------


def test_record_measurement_is_idempotent_per_day(gym):
    with system_context():
        member = register_member(gym, full_name="Measured Member", phone="+9779800000020")

        first = record_measurement(member, date(2026, 10, 1), Decimal("80.00"))
        second = record_measurement(member, date(2026, 10, 1), Decimal("79.50"))

    assert first.pk == second.pk
    assert second.weight_kg == Decimal("79.50")


# --- approve_coaching_report ---------------------------------------------------


def test_approve_coaching_report_notifies_the_member_exactly_once(gym):
    with system_context():
        member = register_member(gym, full_name="Report Member", phone="+9779800000030")
        profile = create_client_profile(
            member,
            trainer=None,
            primary_goal="weight_loss",
            starting_weight_kg=Decimal("80.00"),
            target_weight_kg=Decimal("70.00"),
        )
        report = CoachingReport.objects.create(
            org=gym.org,
            gym=gym,
            member=member,
            week_start=date(2026, 10, 5),
            kind=CoachingReport.Kind.MEMBER,
        )
        trainer_user = None

        with patch("coaching.services.notify") as mock_notify:
            approved = approve_coaching_report(report, trainer_user)

    assert approved.status == CoachingReport.Status.APPROVED
    assert approved.approved_at is not None
    mock_notify.assert_called_once()
    assert mock_notify.call_args.args[1] == "coaching_report_ready"
    assert profile.member_id == member.pk  # sanity: profile really belongs to this member


def test_approve_branch_report_does_not_notify_anyone(gym):
    with system_context():
        report = CoachingReport.objects.create(
            org=gym.org,
            gym=gym,
            member=None,
            week_start=date(2026, 10, 5),
            kind=CoachingReport.Kind.BRANCH,
        )
        with patch("coaching.services.notify") as mock_notify:
            approve_coaching_report(report, None)

    mock_notify.assert_not_called()
