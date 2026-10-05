from __future__ import annotations

import os
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from attendance.models import Attendance
from attendance.services import (
    RedCheckinRequiresReason,
    classify_checkin,
    record_checkins_batch,
    record_manual_checkin,
    register_gate_device,
)
from billing.services import InvoiceLineInput, create_draft_invoice
from core.context import system_context
from gyms.models import Gym, Organization
from members.models import Member, Membership, Plan

pytestmark = pytest.mark.django_db

NOW = datetime(2026, 10, 4, 10, 0, tzinfo=UTC)


@pytest.fixture
def gym():
    with system_context():
        org = Organization.objects.create(name="Attendance Test Org")
        return Gym.objects.create(org=org, code="ATT1", name="Attendance Test Gym")


@pytest.fixture
def plan(gym):
    with system_context():
        return Plan.objects.create(
            org=gym.org, gym=gym, name="Monthly", duration_days=30, price_npr=Decimal("3000.00")
        )


def _make_member(gym, **overrides):
    defaults = dict(
        org=gym.org,
        gym=gym,
        member_code=f"ATT1-{uuid.uuid4().hex[:6]}",
        full_name="Test Member",
        phone=f"+9779{uuid.uuid4().int % 10**9:09d}",
        qr_secret=os.urandom(32),
        status=Member.Status.ACTIVE,
    )
    defaults.update(overrides)
    return Member.objects.create(**defaults)


def _make_membership(member, plan, start_date, expiry_date):
    return Membership.objects.create(
        org=member.org,
        gym=member.gym,
        member=member,
        plan=plan,
        start_date=start_date,
        expiry_date=expiry_date,
        status=Membership.Status.ACTIVE,
    )


# --- register_gate_device --------------------------------------------------


def test_register_gate_device_returns_device_and_token(gym):
    device, token = register_gate_device(gym, "Front Gate")
    assert device.name == "Front Gate"
    assert device.gym_id == gym.pk
    assert len(token) > 20
    # The stored hash must not be (and cannot be reversed to) the raw token.
    assert device.device_key_hash != token


# --- classify_checkin --------------------------------------------------


def test_classify_green_for_healthy_active_member(gym, plan):
    with system_context():
        member = _make_member(gym)
        _make_membership(member, plan, date(2026, 10, 1), date(2026, 10, 31))
    assert classify_checkin(member, NOW) == "green"


def test_classify_red_for_frozen_member(gym):
    with system_context():
        member = _make_member(gym, status=Member.Status.FROZEN)
    assert classify_checkin(member, NOW) == "red"


def test_classify_red_for_expired_membership(gym, plan):
    with system_context():
        member = _make_member(gym)
        _make_membership(member, plan, date(2026, 9, 1), date(2026, 9, 30))
        assert classify_checkin(member, NOW) == "red"


def test_classify_amber_near_expiry(gym, plan):
    with system_context():
        member = _make_member(gym)
        _make_membership(member, plan, date(2026, 9, 5), date(2026, 10, 6))  # 2 days left
        assert classify_checkin(member, NOW) == "amber"


def test_classify_red_for_unpaid_dues(gym, plan):
    with system_context():
        member = _make_member(gym)
        _make_membership(member, plan, date(2026, 10, 1), date(2026, 10, 31))
        create_draft_invoice(
            gym,
            member,
            [InvoiceLineInput("Monthly", 1, Decimal("3000.00"), Decimal("3000.00"))],
            Decimal("3000.00"),
            Decimal("0.00"),
            Decimal("3000.00"),
            today=NOW.date(),
        )
        assert classify_checkin(member, NOW) == "red"


# --- record_manual_checkin --------------------------------------------------


def test_manual_checkin_green_member_no_reason_needed(gym, plan):
    with system_context():
        member = _make_member(gym)
        _make_membership(member, plan, date(2026, 10, 1), date(2026, 10, 31))
        attendance = record_manual_checkin(member, actor=None, now=NOW)
    assert attendance.source == Attendance.Source.FRONT_DESK_MANUAL
    assert attendance.correction_reason == ""


def test_manual_checkin_red_member_requires_reason(gym):
    with system_context():
        member = _make_member(gym, status=Member.Status.FROZEN)
        with pytest.raises(RedCheckinRequiresReason):
            record_manual_checkin(member, actor=None, now=NOW)


def test_manual_checkin_red_member_with_reason_succeeds(gym):
    with system_context():
        member = _make_member(gym, status=Member.Status.FROZEN)
        attendance = record_manual_checkin(
            member, actor=None, reason="Owner approved one-time entry", now=NOW
        )
    assert attendance.correction_reason == "Owner approved one-time entry"


def test_manual_checkin_updates_last_check_in_at(gym, plan):
    with system_context():
        member = _make_member(gym)
        _make_membership(member, plan, date(2026, 10, 1), date(2026, 10, 31))
        record_manual_checkin(member, actor=None, now=NOW)
        member.refresh_from_db()
    assert member.last_check_in_at == NOW


def test_manual_checkin_anti_passback_requires_reason(gym, plan):
    with system_context():
        member = _make_member(gym)
        _make_membership(member, plan, date(2026, 10, 1), date(2026, 10, 31))
        record_manual_checkin(member, actor=None, now=NOW)
        # Same member, 2 minutes later — inside the default 5-minute window.
        with pytest.raises(RedCheckinRequiresReason):
            record_manual_checkin(member, actor=None, now=NOW + timedelta(minutes=2))


# --- record_checkins_batch --------------------------------------------------


def test_batch_accepts_new_checkins(gym):
    with system_context():
        member = _make_member(gym)
        result = record_checkins_batch(
            register_gate_device(gym, "Gate")[0],
            [
                {
                    "client_uuid": uuid.uuid4(),
                    "member_code": member.member_code,
                    "check_in_at": NOW,
                    "source": Attendance.Source.QR_GATE,
                }
            ],
        )
    assert len(result["accepted"]) == 1
    assert result["duplicates"] == []
    assert result["rejected"] == []


def test_batch_rejects_unknown_member_code(gym):
    with system_context():
        device, _ = register_gate_device(gym, "Gate")
        result = record_checkins_batch(
            device,
            [
                {
                    "client_uuid": uuid.uuid4(),
                    "member_code": "DOES-NOT-EXIST",
                    "check_in_at": NOW,
                    "source": Attendance.Source.QR_GATE,
                }
            ],
        )
    assert result["accepted"] == []
    assert len(result["rejected"]) == 1


def test_batch_replay_is_idempotent_zero_new_duplicates(gym):
    """The exact scenario the Playwright offline-sync test exercises at HTTP
    level: replaying the identical outbox produces 0 new rows, every
    client_uuid reported as a duplicate the second time."""
    with system_context():
        member = _make_member(gym)
        device, _ = register_gate_device(gym, "Gate")
        rows = [
            {
                "client_uuid": uuid.uuid4(),
                "member_code": member.member_code,
                "check_in_at": NOW + timedelta(seconds=i),
                "source": Attendance.Source.QR_GATE,
            }
            for i in range(5)
        ]

        first = record_checkins_batch(device, rows)
        second = record_checkins_batch(device, rows)

        assert len(first["accepted"]) == 5
        assert second["accepted"] == []
        assert len(second["duplicates"]) == 5
        assert Attendance.objects.filter(member=member).count() == 5


def test_batch_updates_last_check_in_at_to_latest(gym):
    with system_context():
        member = _make_member(gym)
        device, _ = register_gate_device(gym, "Gate")
        rows = [
            {
                "client_uuid": uuid.uuid4(),
                "member_code": member.member_code,
                "check_in_at": NOW,
                "source": Attendance.Source.QR_GATE,
            },
            {
                "client_uuid": uuid.uuid4(),
                "member_code": member.member_code,
                "check_in_at": NOW + timedelta(hours=1),
                "source": Attendance.Source.QR_GATE,
            },
        ]
        record_checkins_batch(device, rows)
        member.refresh_from_db()

    assert member.last_check_in_at == NOW + timedelta(hours=1)
