"""Business logic for freezes, call-queue completion, and campaigns. Rule 9:
views stay thin, this is where it actually lives.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from core.services import audit
from members.models import Member, Membership, PromoCode
from notifications.services import notify
from retention.domain.freeze import apply_freeze, revert_freeze
from retention.models import Campaign, FreezeRequest, MembershipFreeze, RetentionCall

WINBACK_WINDOWS_DAYS: dict[str, int] = {
    Campaign.Kind.WINBACK_30: 30,
    Campaign.Kind.WINBACK_60: 60,
    Campaign.Kind.WINBACK_90: 90,
}
WINBACK_GRACE_DAYS = 2


class MaxFreezeDaysExceeded(ValueError):
    pass


def _frozen_days_used(membership: Membership) -> int:
    total = MembershipFreeze.objects.filter(
        membership=membership, reverted_at__isnull=True
    ).aggregate(total=Sum("days"))["total"]
    return total or 0


def apply_individual_freeze(
    membership: Membership,
    start: date,
    end: date,
    reason: str,
    actor: Any = None,
    fee_npr: Decimal = Decimal("0"),
) -> MembershipFreeze:
    """FR-5.9: enforces plan.max_freeze_days across this membership's
    lifetime (sum of every non-reverted freeze), not just this one call.
    """
    new_expiry, days = apply_freeze(membership.expiry_date, start, end)
    already_used = _frozen_days_used(membership)
    max_days = membership.plan.max_freeze_days
    if max_days and already_used + days > max_days:
        raise MaxFreezeDaysExceeded(
            f"This membership has {max_days} max freeze days; "
            f"{already_used} already used, {days} more would exceed it."
        )

    with transaction.atomic():
        previous_expiry = membership.expiry_date
        freeze = MembershipFreeze.objects.create(
            org=membership.org,
            gym=membership.gym,
            membership=membership,
            batch_id=uuid.uuid4(),
            reason=reason,
            start_date=start,
            end_date=end,
            days=days,
            previous_expiry=previous_expiry,
            fee_npr=fee_npr,
            created_by=actor,
        )
        membership.expiry_date = new_expiry
        membership.save(update_fields=["expiry_date"])
        member = membership.member
        member.status = Member.Status.FROZEN
        member.save(update_fields=["status"])
        audit(
            freeze,
            "create",
            after={
                "days": days,
                "previous_expiry": str(previous_expiry),
                "new_expiry": str(new_expiry),
            },
            actor=actor,
        )
        notify(
            member,
            "freeze_applied",
            {"start_date": str(start), "end_date": str(end)},
            actor=actor,
        )
    return freeze


@dataclass
class FreezePreviewRow:
    member_id: Any
    member_name: str
    membership_id: Any
    previous_expiry: date
    new_expiry: date
    would_exceed_max: bool


def preview_bulk_freeze(gym: Any, start: date, end: date) -> list[FreezePreviewRow]:
    """Read-only (FR-5.8): no writes, just what a confirm would do."""
    rows: list[FreezePreviewRow] = []
    memberships = Membership.objects.filter(
        gym=gym, status=Membership.Status.ACTIVE
    ).select_related("member", "plan")
    for membership in memberships:
        new_expiry, days = apply_freeze(membership.expiry_date, start, end)
        already_used = _frozen_days_used(membership)
        max_days = membership.plan.max_freeze_days
        would_exceed = bool(max_days and already_used + days > max_days)
        rows.append(
            FreezePreviewRow(
                member_id=membership.member_id,
                member_name=membership.member.full_name,
                membership_id=membership.pk,
                previous_expiry=membership.expiry_date,
                new_expiry=new_expiry,
                would_exceed_max=would_exceed,
            )
        )
    return rows


def confirm_bulk_freeze(
    gym: Any, start: date, end: date, reason: str, actor: Any = None
) -> uuid.UUID:
    """FR-5.8: one batch_id for the whole festival freeze. Memberships that
    would exceed their plan's max_freeze_days are skipped, not frozen partway.
    """
    batch_id = uuid.uuid4()
    memberships = Membership.objects.filter(
        gym=gym, status=Membership.Status.ACTIVE
    ).select_related("member", "plan")

    with transaction.atomic():
        for membership in memberships:
            new_expiry, days = apply_freeze(membership.expiry_date, start, end)
            already_used = _frozen_days_used(membership)
            max_days = membership.plan.max_freeze_days
            if max_days and already_used + days > max_days:
                continue

            previous_expiry = membership.expiry_date
            freeze = MembershipFreeze.objects.create(
                org=membership.org,
                gym=membership.gym,
                membership=membership,
                batch_id=batch_id,
                reason=reason,
                start_date=start,
                end_date=end,
                days=days,
                previous_expiry=previous_expiry,
                created_by=actor,
            )
            membership.expiry_date = new_expiry
            membership.save(update_fields=["expiry_date"])
            member = membership.member
            member.status = Member.Status.FROZEN
            member.save(update_fields=["status"])
            audit(
                freeze,
                "create",
                after={"batch_id": str(batch_id), "days": days},
                actor=actor,
            )
            notify(
                member,
                "freeze_applied",
                {"start_date": str(start), "end_date": str(end)},
                actor=actor,
            )
    return batch_id


def revert_freeze_batch(batch_id: uuid.UUID, gym: Any, actor: Any = None) -> int:
    """Undo (FR-5.8): restores previous_expiry exactly for every un-reverted
    freeze in this batch.
    """
    reverted = 0
    freezes = MembershipFreeze.objects.filter(
        batch_id=batch_id, gym=gym, reverted_at__isnull=True
    ).select_related("membership__member")

    with transaction.atomic():
        for freeze in freezes:
            membership = freeze.membership
            restored_expiry = revert_freeze(membership.expiry_date, freeze.days)
            membership.expiry_date = restored_expiry
            membership.save(update_fields=["expiry_date"])

            member = membership.member
            if member.status == Member.Status.FROZEN:
                member.status = Member.Status.ACTIVE
                member.save(update_fields=["status"])

            freeze.reverted_at = timezone.now()
            freeze.save(update_fields=["reverted_at"])
            audit(
                freeze,
                "update",
                after={"reverted": True, "restored_expiry": str(restored_expiry)},
                actor=actor,
            )
            reverted += 1
    return reverted


# --- Member-initiated freeze requests (FR-8.6) -------------------------


def request_freeze(
    member: Member, membership: Membership, start: date, end: date, reason: str
) -> FreezeRequest:
    """Just creates the pending row -- the freeze-days check happens once,
    at approval time, by apply_individual_freeze itself. Duplicating it
    here would let a request look valid now and fail later anyway.
    """
    freeze_request = FreezeRequest.objects.create(
        org=member.org,
        gym=member.gym,
        member=member,
        membership=membership,
        start_date=start,
        end_date=end,
        reason=reason,
    )
    audit(freeze_request, "create", after={"status": "pending"})
    return freeze_request


def approve_freeze_request(freeze_request: FreezeRequest, actor: Any) -> FreezeRequest:
    """Lets MaxFreezeDaysExceeded propagate uncommitted -- a request that
    would exceed the plan's max_freeze_days stays pending, not partially
    applied.
    """
    apply_individual_freeze(
        freeze_request.membership,
        freeze_request.start_date,
        freeze_request.end_date,
        freeze_request.reason,
        actor=actor,
    )
    freeze_request.status = FreezeRequest.Status.APPROVED
    freeze_request.reviewed_by = actor
    freeze_request.reviewed_at = timezone.now()
    freeze_request.save(update_fields=["status", "reviewed_by", "reviewed_at"])
    audit(freeze_request, "update", after={"status": "approved"}, actor=actor)
    return freeze_request


def reject_freeze_request(freeze_request: FreezeRequest, actor: Any) -> FreezeRequest:
    freeze_request.status = FreezeRequest.Status.REJECTED
    freeze_request.reviewed_by = actor
    freeze_request.reviewed_at = timezone.now()
    freeze_request.save(update_fields=["status", "reviewed_by", "reviewed_at"])
    audit(freeze_request, "update", after={"status": "rejected"}, actor=actor)
    return freeze_request


def complete_call(
    call: RetentionCall, outcome: str, call_back_on: date | None = None, notes: str = ""
) -> RetentionCall:
    """The only way a RetentionCall gets an outcome (FR-5.5) -- outcome is a
    required serializer field at the view layer, this just persists it.
    """
    call.outcome = outcome
    call.call_back_on = call_back_on
    call.notes = notes
    call.completed_at = timezone.now()
    call.save(update_fields=["outcome", "call_back_on", "notes", "completed_at"])
    return call


# --- Campaigns ---------------------------------------------------------


def _winback_eligible_members(gym: Any, kind: str, as_of: date) -> list[Member]:
    """Members whose most recent membership expired `window` days before
    `as_of` (+/- WINBACK_GRACE_DAYS), and who've opted in to marketing.
    """
    window = WINBACK_WINDOWS_DAYS[kind]
    target = as_of - timedelta(days=window)
    low = target - timedelta(days=WINBACK_GRACE_DAYS)
    high = target + timedelta(days=WINBACK_GRACE_DAYS)

    candidate_ids = (
        Membership.objects.filter(
            gym=gym, status=Membership.Status.EXPIRED, expiry_date__gte=low, expiry_date__lte=high
        )
        .values_list("member_id", flat=True)
        .distinct()
    )
    return list(Member.objects.filter(pk__in=candidate_ids, gym=gym, marketing_opt_in=True))


def send_campaign(gym: Any, kind: str, promo: PromoCode | None = None) -> Campaign:
    """Routed through notify() (FR-6.8) rather than get_sms_provider()
    directly, so winback gets the same opt-out/quiet-hours/wallet/fallback
    protections every other notification gets, for free. _winback_eligible_
    members() already filters on marketing_opt_in — notify()'s own
    notifications_opt_out check composes with that rather than replacing it.
    """
    today = date.today()
    eligible = _winback_eligible_members(gym, kind, today)

    campaign = Campaign.objects.create(
        org=gym.org, gym=gym, kind=kind, promo=promo, sent_count=len(eligible)
    )

    for member in eligible:
        context = {"name": member.full_name, "promo_code": promo.code if promo else ""}
        notify(member, "winback", context)
    return campaign


def recompute_campaign_conversions(campaign: Campaign) -> int:
    """Re-derives who was eligible when this campaign was sent, and counts
    how many have since started a new membership -- no per-recipient table
    needed, this is fully re-derivable from Membership rows.
    """
    sent_on = campaign.created_at.date()
    eligible = _winback_eligible_members(campaign.gym, campaign.kind, sent_on)
    eligible_ids = [m.pk for m in eligible]

    converted = (
        Membership.objects.filter(
            gym=campaign.gym, member_id__in=eligible_ids, start_date__gt=sent_on
        )
        .values_list("member_id", flat=True)
        .distinct()
        .count()
    )
    campaign.converted_count = converted
    campaign.save(update_fields=["converted_count"])
    return converted
