"""Business logic for Phase 11: feature gating, member limits, billing
generation, dunning, payment confirmation, impersonation, export/deletion.
Rule 9: views/tasks stay thin, this is where it actually lives. Everything
here runs under core.context.system_context() — these models carry no RLS
(see saas/models.py's module docstring).
"""

from __future__ import annotations

import hashlib
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.utils import timezone

from accounts.models import StaffRole, User
from billing.domain.vat import vat_for_line
from core.context import system_context
from core.domain.bs import to_bs
from members.models import Member
from notifications.models import SmsWallet, SmsWalletTx
from notifications.providers import email as email_provider
from notifications.providers import whatsapp as whatsapp_provider
from saas.domain.dunning import next_status
from saas.domain.pricing import amount_for
from saas.models import (
    FeatureFlag,
    PlatformAuditLog,
    SaasInvoice,
    SaasInvoiceCounter,
    SaasPlan,
    Subscription,
)

TRIAL_DAYS = 14
# Nepali fiscal year runs Shrawan 1 (BS month 4) to the following Asar's
# end — same rule billing/services.py's own _fiscal_year_for duplicates
# from core.domain.nptime.fiscal_year() for the same reason stated there:
# that helper returns a display string, this needs the bare start-year int.
_FISCAL_YEAR_START_MONTH = 4


def _fiscal_year_for(d: date) -> int:
    bs_year, bs_month, _ = to_bs(d)
    return bs_year if bs_month >= _FISCAL_YEAR_START_MONTH else bs_year - 1


def log_platform_action(
    org: Any,
    action: str,
    *,
    actor: Any = None,
    target: Any = None,
    reason: str = "",
    before: dict | None = None,
    after: dict | None = None,
) -> PlatformAuditLog:
    return PlatformAuditLog.objects.create(
        actor=actor,
        org=org,
        action=action,
        target_type=target._meta.db_table if target is not None else "",
        target_id=str(target.pk) if target is not None else "",
        reason=reason,
        before=before,
        after=after,
    )


def _owners_for(org: Any) -> list[StaffRole]:
    return list(
        StaffRole.objects.filter(org=org, role=StaffRole.Role.OWNER, is_active=True)
        .select_related("user")
    )


# --- Feature gating — FR-11.2 ------------------------------------------------


def has_feature(org: Any, key: str) -> bool:
    """Resolution order: explicit per-org FeatureFlag override > deterministic
    rollout_pct hash > the org's current plan's `features` dict > the
    FeatureFlag's own default > True (undeclared keys are open by default —
    gating is opt-in per key, not a global allowlist).
    """
    flag = FeatureFlag.objects.filter(key=key).first()
    if flag is not None:
        override = flag.per_org_overrides.get(str(org.pk))
        if override is not None:
            return bool(override)
        if flag.rollout_pct is not None:
            digest = hashlib.sha256(f"{org.pk}:{key}".encode()).hexdigest()
            bucket = int(digest, 16) % 100
            return bucket < flag.rollout_pct

    sub = Subscription.objects.filter(org=org).select_related("plan").first()
    if sub is not None and key in sub.plan.features:
        return bool(sub.plan.features[key])

    if flag is not None:
        return flag.default

    return True


# --- Member limits — FR-11.2 --------------------------------------------------


class MemberLimitExceeded(ValueError):
    pass


def check_member_limit(gym: Any) -> None:
    """Counted org-wide (summed across all the org's gyms) — a SaaS seat
    limit, not a per-branch one. Enterprise's member_limit is None
    (unlimited) regardless of branch count.
    """
    sub = Subscription.objects.filter(org=gym.org).select_related("plan").first()
    if sub is None or sub.plan.member_limit is None:
        return
    current = Member.objects.filter(org=gym.org).count()
    if current >= sub.plan.member_limit:
        raise MemberLimitExceeded(
            f"Member limit reached for the {sub.plan.code} plan "
            f"({sub.plan.member_limit} members)."
        )


# --- Trial / onboarding -------------------------------------------------------


def start_trial(org: Any, plan_code: str = SaasPlan.Code.STARTER) -> Subscription:
    today = timezone.localdate()
    plan = SaasPlan.objects.get(code=plan_code)
    return Subscription.objects.create(
        org=org,
        plan=plan,
        billing_cycle=Subscription.BillingCycle.MONTHLY,
        branches=1,
        current_period_start=today,
        current_period_end=today + timedelta(days=TRIAL_DAYS),
        status=Subscription.Status.TRIAL,
    )


# --- Billing generation — FR-11.3 ---------------------------------------------


def _next_invoice_number(today: date) -> str:
    fiscal_year = _fiscal_year_for(today)
    with transaction.atomic():
        counter, _ = SaasInvoiceCounter.objects.select_for_update().get_or_create(
            fiscal_year=fiscal_year
        )
        counter.last_value += 1
        counter.save(update_fields=["last_value"])
        return f"FK-{fiscal_year}-{counter.last_value:05d}"


def _issue_invoice(
    org: Any, *, kind: str, label: str, amount_npr: Decimal, period: date | None = None
) -> SaasInvoice:
    today = timezone.localdate()
    # FitKhata's own plan prices are VAT-exclusive — VAT added on top.
    vat = vat_for_line(amount_npr, inclusive=False)
    invoice = SaasInvoice.objects.create(
        org=org,
        kind=kind,
        number=_next_invoice_number(today),
        period=period,
        lines=[{"label": label, "amount_npr": str(amount_npr)}],
        subtotal_npr=vat.taxable_npr,
        vat_npr=vat.vat_npr,
        total_npr=vat.total_npr,
        status=SaasInvoice.Status.ISSUED,
    )
    log_platform_action(
        org, "saas_invoice_issued", target=invoice, after={"total_npr": str(vat.total_npr)}
    )
    return invoice


def generate_monthly_invoices(today: date | None = None) -> list[SaasInvoice]:
    """FR-11.3, 01:00 Asia/Kathmandu on the 1st. Bills every subscription
    still taking traffic (active/grace/read_only) whose current period has
    elapsed; TRIAL/SUSPENDED/CANCELLED subscriptions aren't auto-billed —
    trial conversion and reactivation are separate, explicit actions.
    """
    today = today or timezone.localdate()
    created: list[SaasInvoice] = []
    with system_context():
        subs = Subscription.objects.select_related("plan", "org").filter(
            status__in=[
                Subscription.Status.ACTIVE,
                Subscription.Status.GRACE,
                Subscription.Status.READ_ONLY,
            ],
            current_period_end__lte=today,
        )
        for sub in subs:
            amount = amount_for(sub.plan, sub.billing_cycle, sub.branches)
            invoice = _issue_invoice(
                sub.org,
                kind=SaasInvoice.Kind.SUBSCRIPTION,
                label=f"{sub.plan.code} plan — {sub.billing_cycle}",
                amount_npr=amount,
                period=sub.current_period_end.replace(day=1),
            )
            created.append(invoice)
            period_days = 30 if sub.billing_cycle == Subscription.BillingCycle.MONTHLY else 365
            sub.current_period_start = sub.current_period_end
            sub.current_period_end = sub.current_period_end + timedelta(days=period_days)
            sub.save(update_fields=["current_period_start", "current_period_end"])
    return created


# --- Dunning — FR-11.3 ---------------------------------------------------------


def transition_subscription(sub: Subscription, new_status: str, *, actor: Any = None) -> None:
    before = sub.status
    sub.status = new_status
    if new_status == Subscription.Status.GRACE and sub.grace_entered_at is None:
        sub.grace_entered_at = timezone.localdate()
    sub.save(update_fields=["status", "grace_entered_at"])
    log_platform_action(
        sub.org,
        "subscription_status_changed",
        actor=actor,
        target=sub,
        before={"status": before},
        after={"status": new_status},
    )


def _send_dunning_reminder(sub: Subscription, days: int) -> None:
    for owner_role in _owners_for(sub.org):
        user = owner_role.user
        body = (
            f"Your FitKhata subscription payment is {days} day(s) overdue. "
            "Please pay to avoid losing access."
        )
        if user.email:
            email_provider.send(user.email, "FitKhata — payment overdue", body)
        if user.phone:
            whatsapp_provider.send(
                user.phone, "fitkhata_dunning_reminder", "en", [sub.org.name, str(days)]
            )


def run_dunning_sweep(today: date | None = None) -> None:
    """FR-11.3 daily sweep. Walks every subscription with a grace_entered_at
    set (i.e. currently mid-dunning) plus any ACTIVE subscription whose
    latest issued invoice is unpaid (entering dunning for the first time).
    """
    today = today or timezone.localdate()
    with system_context():
        candidates = Subscription.objects.select_related("org", "plan").filter(
            status__in=[
                Subscription.Status.ACTIVE,
                Subscription.Status.GRACE,
                Subscription.Status.READ_ONLY,
            ]
        )
        for sub in candidates:
            unpaid = (
                SaasInvoice.objects.filter(
                    org=sub.org,
                    kind=SaasInvoice.Kind.SUBSCRIPTION,
                    status=SaasInvoice.Status.ISSUED,
                )
                .order_by("-created_at")
                .first()
            )
            if unpaid is None:
                continue
            anchor = sub.grace_entered_at or unpaid.created_at.date()
            days = (today - anchor).days
            new_status = next_status(sub.status, days)
            if new_status is not None:
                transition_subscription(sub, new_status)
            if days in (3, 5, 7):
                _send_dunning_reminder(sub, days)


# --- Payment confirmation ------------------------------------------------------


def _restore_subscription(org: Any, *, actor: Any = None) -> None:
    sub = Subscription.objects.select_for_update().filter(org=org).first()
    if sub is None or sub.status == Subscription.Status.ACTIVE:
        return
    transition_subscription(sub, Subscription.Status.ACTIVE, actor=actor)


def _credit_sms_wallet(org: Any, amount_npr: Decimal) -> None:
    wallet, _ = SmsWallet.objects.select_for_update().get_or_create(org=org)
    wallet.balance_npr += amount_npr
    wallet.save(update_fields=["balance_npr"])
    SmsWalletTx.objects.create(
        wallet=wallet, amount_npr=amount_npr, reason=SmsWalletTx.Reason.TOPUP
    )


def confirm_saas_invoice_payment(
    invoice: SaasInvoice,
    *,
    paid_via: str,
    gateway_ref: str = "",
    raw_response: dict | None = None,
    actor: Any = None,
) -> SaasInvoice:
    """Idempotent on invoice.pk — mirrors billing/services.py::
    collect_payment's select_for_update + early-return-if-already-settled
    shape, without that function's tenant-specific side effects.
    """
    with transaction.atomic(), system_context():
        locked = SaasInvoice.objects.select_for_update().get(pk=invoice.pk)
        if locked.status == SaasInvoice.Status.PAID:
            return locked
        locked.status = SaasInvoice.Status.PAID
        locked.paid_via = paid_via
        locked.paid_at = timezone.now()
        locked.save(update_fields=["status", "paid_via", "paid_at"])
        log_platform_action(
            locked.org,
            "saas_invoice_paid",
            actor=actor,
            target=locked,
            after={"paid_via": paid_via, "gateway_ref": gateway_ref, "raw_response": raw_response},
        )
        if locked.kind == SaasInvoice.Kind.SUBSCRIPTION:
            _restore_subscription(locked.org, actor=actor)
        else:
            _credit_sms_wallet(locked.org, locked.total_npr)
        return locked


def initiate_sms_topup_invoice(org: Any, amount_npr: Decimal) -> SaasInvoice:
    with system_context():
        return _issue_invoice(
            org, kind=SaasInvoice.Kind.SMS_TOPUP, label="SMS credits top-up", amount_npr=amount_npr
        )


# --- Impersonation — FR-11.6 ---------------------------------------------------

IMPERSONATION_MINUTES = 30


def start_impersonation(platform_user: User, org: Any, reason: str) -> dict[str, Any]:
    """Issues a short-lived access token for the org's owner, carrying an
    `impersonator_id` claim every subsequent request made with it attaches
    to both the normal AuditLog (actor=owner, unchanged) and a parallel
    PlatformAuditLog row (see core/middleware.py's reading of this claim).
    """
    from rest_framework_simplejwt.tokens import AccessToken

    with system_context():
        owner_role = StaffRole.objects.filter(
            org=org, role=StaffRole.Role.OWNER, is_active=True
        ).select_related("user").first()
        if owner_role is None:
            raise ValueError("This organization has no active owner to impersonate.")
        gym_ids = sorted(str(gym_id) for gym_id in org.gyms.values_list("id", flat=True))

    token = AccessToken.for_user(owner_role.user)
    token.set_exp(lifetime=timedelta(minutes=IMPERSONATION_MINUTES))
    token["impersonator_id"] = str(platform_user.pk)
    # Same claims issue_tokens_for_user sets — without these the admin
    # nav's client-side role gate (canSee(claims.role, ...)) hides every
    # section but Dashboard, defeating the point of impersonating.
    token["org_id"] = str(org.pk)
    token["gym_ids"] = gym_ids
    token["role"] = owner_role.role

    log_platform_action(
        org,
        "impersonation_started",
        actor=platform_user,
        reason=reason,
        after={"target_user_id": str(owner_role.user_id)},
    )
    return {"access": str(token), "org_id": str(org.pk), "expires_in": IMPERSONATION_MINUTES * 60}


# --- Data export & account deletion — FR-11.7 ----------------------------------


def export_org_data_rows(org: Any) -> dict[str, list[Any]]:
    """Returns {csv_filename: [row_dict, ...]} for every tenant model the
    org owns — saas/tasks.py zips these to CSVs. Kept as a pure data-
    gathering function (no storage/zip I/O) so it's unit-testable without
    touching Celery/object storage.
    """
    from attendance.models import Attendance
    from billing.models import Invoice, Payment
    from members.models import Member, Membership

    with system_context():
        return {
            "members.csv": list(
                Member.objects.filter(org=org).values(
                    "member_code", "full_name", "phone", "status", "created_at"
                )
            ),
            "memberships.csv": list(
                Membership.objects.filter(org=org).values(
                    "member__member_code", "plan__name", "start_date", "expiry_date", "status"
                )
            ),
            "invoices.csv": list(
                Invoice.objects.filter(org=org).values(
                    "number", "bill_date", "total_npr", "status"
                )
            ),
            "payments.csv": list(
                Payment.objects.filter(org=org).values(
                    "transaction_uuid", "amount_npr", "mode", "status", "created_at"
                )
            ),
            "attendance.csv": list(
                Attendance.objects.filter(org=org).values(
                    "member__member_code", "check_in_at", "source"
                )
            ),
        }


ACCOUNT_DELETION_GRACE_DAYS = 30


def schedule_account_deletion(org: Any) -> None:
    with system_context():
        Subscription.objects.filter(org=org).update(
            deletion_requested_at=timezone.localdate(), status=Subscription.Status.CANCELLED
        )
    log_platform_action(org, "deletion_requested")


def _anonymized_phone(member_id: Any) -> str:
    # Deterministic but unidentifiable — keeps the unique phone constraint
    # satisfiable without leaking anything derivable back to the real number.
    digest = hashlib.sha256(str(member_id).encode()).hexdigest()[:8]
    return f"+977000{digest}"[:14]


def anonymize_org(org: Any) -> int:
    """FR-11.7: scrubs member PII in place (rule 8's void-not-delete spirit
    applied here) rather than hard-deleting rows other tables still
    reference. Returns the number of members anonymized.
    """
    with system_context():
        members = list(Member.objects.filter(org=org))
        for member in members:
            member.full_name = "Deleted member"
            member.phone = _anonymized_phone(member.pk)
            member.photo = None
            member.emergency_contact = {}
            member.save(update_fields=["full_name", "phone", "photo", "emergency_contact"])
        Subscription.objects.filter(org=org).update(anonymized_at=timezone.now())
        log_platform_action(org, "org_anonymized", after={"member_count": len(members)})
        return len(members)
