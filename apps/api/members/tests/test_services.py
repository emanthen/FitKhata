from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.db import IntegrityError

from billing.models import Payment
from billing.services import collect_payment
from core.context import system_context
from gyms.models import Gym, Organization
from members.models import AddOn, Plan, PromoCode
from members.services import PromoNotApplicable, register_member, sell_membership, transfer_member
from saas.models import SaasPlan, Subscription
from saas.services import MemberLimitExceeded

pytestmark = pytest.mark.django_db


@pytest.fixture
def gym():
    with system_context():
        org = Organization.objects.create(name="Test Org")
        return Gym.objects.create(org=org, code="KTM1", name="Kathmandu Branch")


@pytest.fixture
def other_gym(gym):
    with system_context():
        return Gym.objects.create(org=gym.org, code="PKR1", name="Pokhara Branch")


@pytest.fixture
def plan(gym):
    with system_context():
        return Plan.objects.create(
            org=gym.org, gym=gym, name="Monthly", duration_days=30, price_npr=Decimal("3000.00")
        )


def test_register_member_allocates_sequential_codes(gym):
    with system_context():
        m1 = register_member(gym, full_name="Ram Shrestha", phone="+9779800000001")
        m2 = register_member(gym, full_name="Sita Gurung", phone="+9779800000002")
    assert m1.member_code == "KTM1-0001"
    assert m2.member_code == "KTM1-0002"


def test_register_member_duplicate_phone_same_gym_raises(gym):
    with system_context():
        register_member(gym, full_name="Ram Shrestha", phone="+9779800000001")
        with pytest.raises(IntegrityError):
            register_member(gym, full_name="Someone Else", phone="+9779800000001")


def test_register_member_same_phone_different_gym_is_allowed(gym, other_gym):
    with system_context():
        register_member(gym, full_name="Ram Shrestha", phone="+9779800000001")
        # Different gym, same org — should not collide with gym's unique constraint.
        m2 = register_member(other_gym, full_name="Ram Shrestha", phone="+9779800000001")
    assert m2.member_code == "PKR1-0001"


def test_register_member_encrypts_qr_secret(gym):
    with system_context():
        member = register_member(gym, full_name="Ram Shrestha", phone="+9779800000001")
    # Ciphertext should not be the raw 32 bytes, and should decrypt back to 32 bytes.
    from core.crypto import decrypt_bytes

    assert len(bytes(member.qr_secret)) != 32
    assert len(decrypt_bytes(bytes(member.qr_secret))) == 32


def test_register_member_raises_at_plan_member_limit(gym):
    with system_context():
        plan = SaasPlan.objects.get(code=SaasPlan.Code.STARTER)
        plan.member_limit = 1
        plan.save(update_fields=["member_limit"])
        Subscription.objects.create(
            org=gym.org,
            plan=plan,
            billing_cycle=Subscription.BillingCycle.MONTHLY,
            current_period_start=date.today(),
            current_period_end=date.today() + timedelta(days=30),
            status=Subscription.Status.ACTIVE,
        )
        register_member(gym, full_name="Ram Shrestha", phone="+9779800000001")
        with pytest.raises(MemberLimitExceeded):
            register_member(gym, full_name="Sita Gurung", phone="+9779800000002")


def test_sell_membership_creates_invoice_and_dates(gym, plan):
    with system_context():
        member = register_member(gym, full_name="Ram Shrestha", phone="+9779800000001")
        membership = sell_membership(member, plan, today=date(2026, 1, 1))

        assert membership.start_date == date(2026, 1, 1)
        assert membership.expiry_date == date(2026, 1, 30)
        assert membership.invoice is not None
        assert membership.invoice.total_npr == Decimal("3000.00")
        assert membership.invoice.lines.count() == 1
        assert member.memberships.get().status == "active"


def test_sell_membership_early_renewal_abuts_previous_expiry(gym, plan):
    with system_context():
        member = register_member(gym, full_name="Ram Shrestha", phone="+9779800000001")
        first = sell_membership(member, plan, today=date(2026, 1, 1))
        assert first.expiry_date == date(2026, 1, 30)

        # Renew 10 days early — must not lose those days.
        second = sell_membership(member, plan, today=date(2026, 1, 20))

    assert second.start_date == date(2026, 1, 31)
    assert second.expiry_date == date(2026, 3, 1)  # 30 days from Jan 31


def test_sell_membership_with_addons_adds_to_subtotal(gym, plan):
    with system_context():
        addon = AddOn.objects.create(
            org=gym.org, gym=gym, name="Locker", price_npr=Decimal("200.00"), kind="locker"
        )
        member = register_member(gym, full_name="Ram Shrestha", phone="+9779800000001")
        membership = sell_membership(member, plan, addons=[addon], today=date(2026, 1, 1))

        assert membership.invoice.total_npr == Decimal("3200.00")
        assert membership.invoice.lines.count() == 2


def test_sell_membership_applies_flat_promo_and_tracks_redemption(gym, plan):
    with system_context():
        promo = PromoCode.objects.create(
            org=gym.org,
            gym=gym,
            code="WELCOME150",
            kind="flat",
            value=Decimal("150.00"),
            valid_from=date(2026, 1, 1),
            valid_to=date(2026, 12, 31),
        )
        member = register_member(gym, full_name="Ram Shrestha", phone="+9779800000001")
        membership = sell_membership(member, plan, promo=promo, today=date(2026, 1, 1))

        promo.refresh_from_db()

        assert membership.invoice.total_npr == Decimal("2850.00")
        assert promo.times_used == 1
        assert member.promo_redemptions.count() == 1


def test_sell_membership_rejects_reused_per_member_once_promo(gym, plan):
    with system_context():
        promo = PromoCode.objects.create(
            org=gym.org,
            gym=gym,
            code="ONCE",
            kind="flat",
            value=Decimal("100.00"),
            valid_from=date(2026, 1, 1),
            valid_to=date(2026, 12, 31),
            per_member_once=True,
        )
        member = register_member(gym, full_name="Ram Shrestha", phone="+9779800000001")
        sell_membership(member, plan, promo=promo, today=date(2026, 1, 1))

        with pytest.raises(PromoNotApplicable):
            sell_membership(member, plan, promo=promo, today=date(2026, 2, 1))


def test_sell_membership_rejects_promo_outside_validity_window(gym, plan):
    with system_context():
        promo = PromoCode.objects.create(
            org=gym.org,
            gym=gym,
            code="EXPIRED",
            kind="flat",
            value=Decimal("100.00"),
            valid_from=date(2025, 1, 1),
            valid_to=date(2025, 12, 31),
        )
        member = register_member(gym, full_name="Ram Shrestha", phone="+9779800000001")
        with pytest.raises(PromoNotApplicable):
            sell_membership(member, plan, promo=promo, today=date(2026, 1, 1))


def test_transfer_member_moves_to_new_gym_same_org(gym, other_gym):
    with system_context():
        member = register_member(gym, full_name="Ram Shrestha", phone="+9779800000001")

    # Not nested in an outer system_context() here on purpose, just to keep
    # this test honest about transfer_member()'s real call shape — it opens
    # its own internally (it's a cross-tenant write by nature, see its
    # docstring) and nesting is safe either way (core/context.py's depth
    # counting handles it).
    transfer_member(member, other_gym)

    with system_context():
        member.refresh_from_db()

    assert member.gym_id == other_gym.pk


def test_transfer_member_rejects_cross_org(gym):
    with system_context():
        other_org_gym = Gym.objects.create(
            org=Organization.objects.create(name="Other Org"), code="X1", name="Other"
        )
        member = register_member(gym, full_name="Ram Shrestha", phone="+9779800000001")
        with pytest.raises(ValueError, match="same organization"):
            transfer_member(member, other_org_gym)


# --- Referral reward (FR-8.8) -- triggered from billing.services.collect_payment --


def _completed_cash_payment(member, amount=Decimal("1000.00")):
    payment = Payment.objects.create(
        org=member.org,
        gym=member.gym,
        member=member,
        mode=Payment.Mode.CASH,
        channel=Payment.Channel.DESK,
        transaction_uuid=uuid.uuid4(),
        amount_npr=amount,
        status=Payment.Status.PENDING,
    )
    return collect_payment(payment)


def test_reward_referral_triggers_once_on_first_completed_payment(gym, plan):
    with system_context():
        referrer = register_member(gym, full_name="Referrer", phone="+9779800000011")
        referrer_membership = sell_membership(referrer, plan, today=date(2026, 1, 1))
        before_expiry = referrer_membership.expiry_date

        referred = register_member(
            gym, full_name="Referred", phone="+9779800000012", referred_by=referrer
        )

        _completed_cash_payment(referred)
        referrer_membership.refresh_from_db()
        assert referrer_membership.expiry_date == before_expiry + timedelta(days=7)

        # A second completed payment from the same referred member must not
        # reward the referrer again.
        _completed_cash_payment(referred)
        referrer_membership.refresh_from_db()
        assert referrer_membership.expiry_date == before_expiry + timedelta(days=7)


def test_reward_referral_no_op_without_referred_by(gym, plan):
    with system_context():
        referrer = register_member(gym, full_name="Referrer", phone="+9779800000013")
        referrer_membership = sell_membership(referrer, plan, today=date(2026, 1, 1))
        before_expiry = referrer_membership.expiry_date

        not_referred = register_member(gym, full_name="Not Referred", phone="+9779800000014")
        _completed_cash_payment(not_referred)

        referrer_membership.refresh_from_db()
        assert referrer_membership.expiry_date == before_expiry
