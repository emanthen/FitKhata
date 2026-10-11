"""Business logic for members/plans/sales. Rule 9: views stay thin, this is
where register_member / sell_membership / transfer_member actually live.
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from django.db import transaction

from billing.models import Payment
from billing.services import InvoiceLineInput, create_draft_invoice
from core.context import system_context
from core.crypto import encrypt_bytes
from core.services import audit
from members.domain.renewal import apply_promo, expiry_for, next_start
from members.models import (
    AddOn,
    Member,
    MemberCodeCounter,
    MemberFeedback,
    Membership,
    Plan,
    PromoCode,
    PromoCodeRedemption,
)
from notifications.services import notify

REFERRAL_REWARD_DAYS = 7


def register_member(gym: Any, actor: Any = None, **fields: Any) -> Member:
    """Allocates the next member_code under a row lock so concurrent
    registrations at the same gym never collide or leave a gap.
    """
    from saas.services import check_member_limit

    check_member_limit(gym)  # FR-11.2 — raises MemberLimitExceeded, the view maps it to 402

    with transaction.atomic():
        counter, _ = MemberCodeCounter.objects.select_for_update().get_or_create(
            org=gym.org, gym=gym
        )
        counter.last_value += 1
        counter.save(update_fields=["last_value"])
        member_code = f"{gym.code}-{counter.last_value:04d}"

        member = Member.objects.create(
            org=gym.org,
            gym=gym,
            member_code=member_code,
            qr_secret=encrypt_bytes(os.urandom(32)),
            **fields,
        )
        audit(
            member,
            "create",
            after={"member_code": member_code, "full_name": member.full_name},
            actor=actor,
        )
        notify(member, "welcome", {"name": member.full_name}, actor=actor)

        # Lazy import: same cross-app-circular-import shape as this file's
        # other lazy imports (e.g. billing.services's fulfill_renewal_payment).
        from publicapi.services import dispatch_webhook_event

        dispatch_webhook_event(
            gym.org,
            "member.created",
            {"member_id": member.pk, "member_code": member_code, "full_name": member.full_name},
        )
        return member


class PromoNotApplicable(ValueError):
    pass


def _validate_promo(promo: PromoCode, member: Member, today: date) -> None:
    if not (promo.valid_from <= today <= promo.valid_to):
        raise PromoNotApplicable("Promo code is not valid on this date.")
    if promo.usage_limit is not None and promo.times_used >= promo.usage_limit:
        raise PromoNotApplicable("Promo code usage limit reached.")
    if promo.per_member_once and PromoCodeRedemption.objects.filter(
        promo=promo, member=member
    ).exists():
        raise PromoNotApplicable("This member has already used this promo code.")


@dataclass
class _PricedSale:
    lines: list[InvoiceLineInput]
    subtotal_npr: Decimal
    discount_npr: Decimal
    total_npr: Decimal


def _price_sale(plan: Plan, promo: PromoCode | None, addons: list[AddOn]) -> _PricedSale:
    """Shared by sell_membership (desk, pays-and-activates-now) and
    initiate_renewal_payment (online, pays-later) — both need the exact
    same price/discount/line-item math, only what happens *after* pricing
    differs between the two flows.
    """
    plan_price = apply_promo(plan.price_npr, promo)
    discount = (plan.price_npr - plan_price).quantize(Decimal("0.01"))

    plan_description = f"{plan.name} (promo {promo.code})" if promo else plan.name
    lines = [InvoiceLineInput(plan_description, 1, plan.price_npr, plan_price)]
    for addon in addons:
        lines.append(InvoiceLineInput(addon.name, 1, addon.price_npr, addon.price_npr))

    subtotal = plan.price_npr + sum((a.price_npr for a in addons), Decimal("0"))
    total = subtotal - discount
    return _PricedSale(lines=lines, subtotal_npr=subtotal, discount_npr=discount, total_npr=total)


def _redeem_promo(member: Member, promo: PromoCode) -> None:
    PromoCode.objects.filter(pk=promo.pk).update(times_used=promo.times_used + 1)
    PromoCodeRedemption.objects.create(org=member.org, gym=member.gym, promo=promo, member=member)


def sell_membership(
    member: Member,
    plan: Plan,
    actor: Any = None,
    promo: PromoCode | None = None,
    addons: list[AddOn] | None = None,
    today: date | None = None,
) -> Membership:
    today = today or date.today()
    addons = addons or []

    current = member.memberships.order_by("-expiry_date").first()
    start = next_start(today, current.expiry_date if current else None)
    expiry = expiry_for(start, plan.duration_days)

    if promo is not None:
        _validate_promo(promo, member, today)
    priced = _price_sale(plan, promo, addons)

    invoice = create_draft_invoice(
        member.gym,
        member,
        priced.lines,
        priced.subtotal_npr,
        priced.discount_npr,
        priced.total_npr,
        actor,
        today=today,
    )

    membership = Membership.objects.create(
        org=member.org,
        gym=member.gym,
        member=member,
        plan=plan,
        start_date=start,
        expiry_date=expiry,
        status=Membership.Status.ACTIVE,
        invoice=invoice,
    )
    member.status = Member.Status.ACTIVE
    member.save(update_fields=["status"])

    if promo is not None:
        _redeem_promo(member, promo)

    audit(
        membership,
        "create",
        after={"plan": plan.name, "start_date": str(start), "expiry_date": str(expiry)},
        actor=actor,
    )
    return membership


def initiate_renewal_payment(
    member: Member,
    plan: Plan,
    provider: str,
    promo: PromoCode | None = None,
    addons: list[AddOn] | None = None,
    today: date | None = None,
) -> Payment:
    """Member-initiated online renewal (Member PWA, eSewa/Khalti/Fonepay).
    Creates a draft invoice — so the gateway has an amount and a reference
    to redirect against — but deliberately does NOT touch Membership yet:
    unlike the desk flow above, a member here must never get an extension
    for a payment that never completes. fulfill_renewal_payment is the
    other half, run by billing.services.collect_payment() only once the
    gateway actually confirms the money moved. The plan/promo/addon
    selection needed to do that later travels on Payment.metadata — at the
    point fulfill_renewal_payment runs, that's the only record of what
    this payment was for.
    """
    today = today or date.today()
    addons = addons or []

    if promo is not None:
        _validate_promo(promo, member, today)
    priced = _price_sale(plan, promo, addons)

    invoice = create_draft_invoice(
        member.gym,
        member,
        priced.lines,
        priced.subtotal_npr,
        priced.discount_npr,
        priced.total_npr,
        today=today,
    )

    return Payment.objects.create(
        org=member.org,
        gym=member.gym,
        member=member,
        invoice=invoice,
        mode=provider,
        channel=Payment.Channel.ONLINE,
        transaction_uuid=uuid.uuid4(),
        amount_npr=priced.total_npr,
        status=Payment.Status.PENDING,
        metadata={
            "renewal": True,
            "plan_id": plan.pk,
            "promo_code": promo.code if promo else None,
            "addon_ids": [addon.pk for addon in addons],
        },
    )


def fulfill_renewal_payment(payment: Payment, actor: Any = None) -> Membership:
    """The completion half of initiate_renewal_payment — called by
    billing.services.collect_payment() once a Payment carrying
    metadata["renewal"] is confirmed. Re-derives plan/promo/addons from
    that metadata (nothing else links them at this point) and runs the
    exact same start/expiry math sell_membership uses.
    """
    meta = payment.metadata
    member = payment.member
    plan = Plan.objects.get(pk=meta["plan_id"])
    promo = (
        PromoCode.objects.filter(code=meta["promo_code"]).first()
        if meta.get("promo_code")
        else None
    )
    today = (payment.invoice.bill_date if payment.invoice else None) or date.today()

    current = member.memberships.order_by("-expiry_date").first()
    start = next_start(today, current.expiry_date if current else None)
    expiry = expiry_for(start, plan.duration_days)

    membership = Membership.objects.create(
        org=member.org,
        gym=member.gym,
        member=member,
        plan=plan,
        start_date=start,
        expiry_date=expiry,
        status=Membership.Status.ACTIVE,
        invoice=payment.invoice,
    )
    member.status = Member.Status.ACTIVE
    member.save(update_fields=["status"])

    if promo is not None:
        _redeem_promo(member, promo)

    audit(
        membership,
        "create",
        after={
            "plan": plan.name,
            "start_date": str(start),
            "expiry_date": str(expiry),
            "via": "online_renewal",
        },
        actor=actor,
    )
    return membership


def reward_referral(referrer: Member, actor: Any = None, days: int = REFERRAL_REWARD_DAYS) -> None:
    """FR-8.8: extends the referrer's current membership expiry by `days`,
    audited. Called once, by billing.services.collect_payment(), on the
    referred member's first-ever completed payment.
    """
    with transaction.atomic():
        membership = (
            Membership.objects.select_for_update()
            .filter(member=referrer, status=Membership.Status.ACTIVE)
            .order_by("-expiry_date")
            .first()
        )
        if membership is None:
            return
        before_expiry = membership.expiry_date
        membership.expiry_date = before_expiry + timedelta(days=days)
        membership.save(update_fields=["expiry_date"])
        audit(
            membership,
            "update",
            before={"expiry_date": str(before_expiry)},
            after={"expiry_date": str(membership.expiry_date), "reason": "referral_reward"},
            actor=actor,
        )


def _notify_managers(gym: Any, member: Member, message: str) -> None:
    """Direct SMS to gym-or-org-wide managers/owners, bypassing
    notifications.notify() -- same shape as billing.views's
    _notify_owners_of_variance, generalized from owner-only to
    owner-or-manager.
    """
    from django.db.models import Q

    from accounts.models import StaffRole
    from accounts.sms import get_sms_provider

    managers = StaffRole.objects.filter(
        org=gym.org, role__in=[StaffRole.Role.OWNER, StaffRole.Role.MANAGER], is_active=True
    ).filter(Q(gym=gym) | Q(gym__isnull=True)).select_related("user")

    text = (
        f"FitKhata feedback from {member.full_name} ({member.member_code}) "
        f"at {gym.name}: {message}"
    )
    provider = get_sms_provider()
    for staff_role in managers:
        if staff_role.user.phone:
            provider.send(staff_role.user.phone, text)


def submit_feedback(member: Member, message: str) -> MemberFeedback:
    """FR-8.6: a member's complaint/feedback, routed to the branch manager."""
    feedback = MemberFeedback.objects.create(
        org=member.org, gym=member.gym, member=member, message=message
    )
    _notify_managers(member.gym, member, message)
    return feedback


def transfer_member(member: Member, new_gym: Any, actor: Any = None) -> Member:
    """Moves a member to a different branch's gym_id. This is inherently a
    cross-tenant write — the destination gym is, by definition, outside the
    caller's current app.gym_ids session scope, and RLS's USING clause
    doubles as the implicit WITH CHECK on UPDATE, so Postgres would reject
    the write otherwise even though the caller is authorized (checked by
    the view's permission class, same as every other mutation). Hence
    system_context() here, same as every other cross-tenant-boundary write.
    """
    if new_gym.org_id != member.org_id:
        raise ValueError("A member can only transfer between branches of the same organization.")
    before_gym_id = str(member.gym_id)
    with system_context():
        member.gym = new_gym
        member.save(update_fields=["gym"])
        audit(
            member,
            "update",
            before={"gym_id": before_gym_id},
            after={"gym_id": str(new_gym.pk)},
            actor=actor,
        )
    return member
