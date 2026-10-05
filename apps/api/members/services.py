"""Business logic for members/plans/sales. Rule 9: views stay thin, this is
where register_member / sell_membership / transfer_member actually live.
"""

from __future__ import annotations

import os
from datetime import date
from decimal import Decimal
from typing import Any

from django.db import transaction

from billing.services import InvoiceLineInput, create_draft_invoice
from core.context import system_context
from core.crypto import encrypt_bytes
from core.services import audit
from members.domain.renewal import apply_promo, expiry_for, next_start
from members.models import (
    AddOn,
    Member,
    MemberCodeCounter,
    Membership,
    Plan,
    PromoCode,
    PromoCodeRedemption,
)


def register_member(gym: Any, actor: Any = None, **fields: Any) -> Member:
    """Allocates the next member_code under a row lock so concurrent
    registrations at the same gym never collide or leave a gap.
    """
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
    plan_price = apply_promo(plan.price_npr, promo)
    discount = (plan.price_npr - plan_price).quantize(Decimal("0.01"))

    plan_description = f"{plan.name} (promo {promo.code})" if promo else plan.name
    lines = [InvoiceLineInput(plan_description, 1, plan.price_npr, plan_price)]
    for addon in addons:
        lines.append(InvoiceLineInput(addon.name, 1, addon.price_npr, addon.price_npr))

    subtotal = plan.price_npr + sum((a.price_npr for a in addons), Decimal("0"))
    total = subtotal - discount

    invoice = create_draft_invoice(member.gym, member, lines, subtotal, discount, total, actor)

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
        PromoCode.objects.filter(pk=promo.pk).update(times_used=promo.times_used + 1)
        PromoCodeRedemption.objects.create(
            org=member.org, gym=member.gym, promo=promo, member=member
        )

    audit(
        membership,
        "create",
        after={"plan": plan.name, "start_date": str(start), "expiry_date": str(expiry)},
        actor=actor,
    )
    return membership


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
