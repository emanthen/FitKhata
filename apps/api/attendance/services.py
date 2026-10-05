"""Business logic for gate devices and check-ins. Rule 9: views stay thin."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Literal

from django.db import transaction
from django.db.models import Sum
from django.db.models.functions import Greatest

from attendance.models import Attendance, GateDevice
from billing.models import Invoice
from core.context import system_context
from core.domain.nptime import to_kathmandu
from core.services import audit
from members.domain.access import is_within_access_hours
from members.models import Member

Classification = Literal["green", "amber", "red"]
AMBER_THRESHOLD_DAYS = 3


class RedCheckinRequiresReason(ValueError):
    pass


def _broadcast_checkin(attendance: Attendance, member: Member) -> None:
    """Best-effort: a live-feed broadcast failing (e.g. Redis briefly down)
    must never fail the check-in itself — the attendance row is already
    committed by the time this runs.
    """
    from asgiref.sync import async_to_sync
    from channels.layers import get_channel_layer

    from attendance.consumers import group_name_for

    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    try:
        async_to_sync(channel_layer.group_send)(
            group_name_for(str(attendance.gym_id)),
            {
                "type": "checkin.event",
                "payload": {
                    "type": "checkin",
                    "member_code": member.member_code,
                    "full_name": member.full_name,
                    "check_in_at": attendance.check_in_at.isoformat(),
                    "source": attendance.source,
                },
            },
        )
    except Exception:  # broadcast is best-effort, must never fail the check-in
        pass


def register_gate_device(gym: Any, name: str) -> tuple[GateDevice, str]:
    """Returns (device, raw_token) — the only time the raw token is ever
    available; the device must persist it locally, the server never will.

    Called from the unauthenticated pairing flow (attendance.views.GatePairView)
    — no gym is scoped yet (app.gym_ids is empty), so this write needs
    system_context() the same as every other pre-tenant-scoping write.
    """
    raw_token = secrets.token_urlsafe(32)
    with system_context():
        device = GateDevice.objects.create(
            org=gym.org,
            gym=gym,
            name=name,
            device_key_hash=hashlib.sha256(raw_token.encode("utf-8")).hexdigest(),
        )
    return device, raw_token


def member_dues_npr(member: Member) -> Decimal:
    total = Invoice.objects.filter(member=member, status=Invoice.Status.DRAFT).aggregate(
        total=Sum("total_npr")
    )["total"]
    return total or Decimal("0.00")


def classify_checkin(member: Member, now: datetime) -> Classification:
    """Red/amber/green for FR-3.6's "reason required when overriding a red
    result" check. Deliberately simpler than the gate PWA's own local
    validation (lib/gate-validate.ts) — this only needs to answer "would the
    kiosk have shown red", not reproduce every detail (anti-passback is
    checked separately, directly in record_manual_checkin, since it needs a
    gym-scoped recent-Attendance query this function doesn't have gym for).
    """
    if member.status in (Member.Status.EXPIRED, Member.Status.FROZEN, Member.Status.CANCELLED):
        return "red"
    if member_dues_npr(member) > 0:
        return "red"

    membership = member.memberships.order_by("-expiry_date").first()
    if membership is not None:
        days_left = (membership.expiry_date - now.date()).days
        if days_left < 0:
            return "red"
        if days_left <= AMBER_THRESHOLD_DAYS:
            return "amber"
        access_hours = membership.plan.access_hours
        if not is_within_access_hours(access_hours, to_kathmandu(now)):
            return "red"

    return "green"


def _anti_passback_violation(member: Member, gym: Any, now: datetime) -> bool:
    window_min = gym.settings.get("anti_passback_min", 5)
    if window_min <= 0:
        return False
    return Attendance.objects.filter(
        member=member, check_in_at__gte=now - timedelta(minutes=window_min)
    ).exists()


def record_manual_checkin(
    member: Member,
    actor: Any,
    reason: str = "",
    now: datetime | None = None,
) -> Attendance:
    now = now or datetime.now(tz=member.created_at.tzinfo)
    classification = classify_checkin(member, now)
    if _anti_passback_violation(member, member.gym, now):
        classification = "red"

    if classification == "red" and not reason.strip():
        raise RedCheckinRequiresReason(
            "A reason is required to check in a member with a red result."
        )

    with transaction.atomic():
        attendance = Attendance.objects.create(
            org=member.org,
            gym=member.gym,
            member=member,
            check_in_at=now,
            source=Attendance.Source.FRONT_DESK_MANUAL,
            client_uuid=uuid.uuid4(),
            correction_reason=reason,
            created_by=actor,
        )
        # Postgres GREATEST() ignores NULL arguments (returns the non-null
        # one), so this is correct for a member's first-ever check-in too.
        Member.objects.filter(pk=member.pk).update(
            last_check_in_at=Greatest("last_check_in_at", now)
        )
        audit(
            attendance,
            "create",
            after={"source": "front_desk_manual", "classification": classification},
            actor=actor,
        )
    _broadcast_checkin(attendance, member)
    return attendance


def record_checkins_batch(device: GateDevice, rows: list[dict[str, Any]]) -> dict[str, list]:
    """Trusts the device's local validation (it already decided whether to
    let the member through) — this just persists, and reports which rows
    were new vs. already-seen vs. unprocessable. Not re-validating red/
    amber/anti-passback server-side is deliberate: "validation runs locally
    ALWAYS" per spec, the device is the source of truth for the gate
    decision, the server is just recording history.
    """
    client_uuids = [row["client_uuid"] for row in rows]
    existing = set(
        Attendance.objects.filter(client_uuid__in=client_uuids).values_list(
            "client_uuid", flat=True
        )
    )

    accepted: list[str] = []
    duplicates: list[str] = []
    rejected: list[dict[str, str]] = []
    to_create: list[Attendance] = []
    to_broadcast: list[tuple[Attendance, Member]] = []
    member_timestamps: dict[int, datetime] = {}

    for row in rows:
        client_uuid = row["client_uuid"]
        if client_uuid in existing:
            duplicates.append(str(client_uuid))
            continue
        try:
            member = Member.objects.get(gym=device.gym, member_code=row["member_code"])
        except Member.DoesNotExist:
            rejected.append({"client_uuid": str(client_uuid), "reason": "member not found"})
            continue

        check_in_at = row["check_in_at"]
        attendance = Attendance(
            org=device.org,
            gym=device.gym,
            member=member,
            check_in_at=check_in_at,
            source=row.get("source", Attendance.Source.QR_GATE),
            client_uuid=client_uuid,
            device=device,
        )
        to_create.append(attendance)
        to_broadcast.append((attendance, member))
        accepted.append(str(client_uuid))
        if member.pk not in member_timestamps or check_in_at > member_timestamps[member.pk]:
            member_timestamps[member.pk] = check_in_at

    with transaction.atomic():
        if to_create:
            Attendance.objects.bulk_create(to_create, ignore_conflicts=True)
        for member_id, ts in member_timestamps.items():
            Member.objects.filter(pk=member_id).update(
                last_check_in_at=Greatest("last_check_in_at", ts)
            )

    for attendance, member in to_broadcast:
        _broadcast_checkin(attendance, member)

    return {"accepted": accepted, "duplicates": duplicates, "rejected": rejected}
