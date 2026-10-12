"""Platform-level models: FitKhata's own SaaS billing of tenant orgs and the
super-admin console (Phase 11). Deliberately plain models.Model, never
TenantModel — these describe orgs themselves (or FitKhata's own staff
actions), not gym-scoped tenant data, so app.gym_ids-based tenant_isolation_*
policies (core/migrations/0002_rls.py) don't apply to them directly.

They DO carry an org-scoped RLS policy (core/migrations/0004_platform_org_rls.py,
via app_org_ids()) as a backstop, but that's defense-in-depth, not the
primary mechanism — query them only under core.context.system_context()
(SET LOCAL ROLE fitkhata_system, BYPASSRLS), the same precedent
gyms.Organization already sets (see its own docstring). The RLS policy
exists so a future bug that forgets system_context() fails closed (sees
nothing) instead of leaking every org's rows, not so request-scoped code
can read these directly without it.
"""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models


class SaasPlan(models.Model):
    """FR-11.1/SRS §12.1 pricing tiers. Seeded by migrations/0002_seed_plans.py."""

    class Code(models.TextChoices):
        STARTER = "starter", "Starter"
        PRO = "pro", "Pro"
        ENTERPRISE = "enterprise", "Enterprise"

    code = models.CharField(max_length=20, choices=Code.choices, unique=True)
    setup_fee_npr = models.DecimalField(max_digits=12, decimal_places=2)
    monthly_npr = models.DecimalField(max_digits=12, decimal_places=2)
    annual_npr = models.DecimalField(max_digits=12, decimal_places=2)
    # None = unlimited (enterprise). Counted org-wide, see saas/services.py.
    member_limit = models.PositiveIntegerField(null=True, blank=True)
    # Only enterprise sets this — monthly_npr/annual_npr above are already
    # the PER-BRANCH price for it, multiplied by Subscription.branches at
    # invoice time (saas/domain/pricing.py). Avoids an `if code ==
    # "enterprise"` check wherever pricing is computed.
    per_branch_pricing = models.BooleanField(default=False)
    # Plan-tier metadata for pricing/comparison pages — NOT the enforcement
    # mechanism (that's FeatureFlag + has_feature(), see saas/services.py).
    features = models.JSONField(default=dict, blank=True)

    def __str__(self) -> str:
        return self.code


class Subscription(models.Model):
    """One per Organization. Status machine (see saas/domain/dunning.py):
    trial -> active -> grace -> read_only -> suspended, with `cancelled`
    reserved for voluntary/admin cancellation (never reached by the
    automatic dunning sweep). Payment at any point in grace/read_only/
    suspended restores `active` instantly.
    """

    class BillingCycle(models.TextChoices):
        MONTHLY = "monthly", "Monthly"
        ANNUAL = "annual", "Annual"

    class Status(models.TextChoices):
        TRIAL = "trial", "Trial"
        ACTIVE = "active", "Active"
        GRACE = "grace", "Grace"
        READ_ONLY = "read_only", "Read-only"
        SUSPENDED = "suspended", "Suspended"
        CANCELLED = "cancelled", "Cancelled"

    org = models.OneToOneField(
        "gyms.Organization", on_delete=models.CASCADE, related_name="subscription"
    )
    plan = models.ForeignKey(SaasPlan, on_delete=models.PROTECT)
    billing_cycle = models.CharField(max_length=10, choices=BillingCycle.choices)
    branches = models.PositiveIntegerField(default=1)
    current_period_start = models.DateField()
    current_period_end = models.DateField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.TRIAL)
    # Set when the current period's invoice first goes unpaid — anchors the
    # day-3/5/7/8/30 dunning clock without recomputing "days since invoice"
    # on every sweep run. Cleared back to null on payment/renewal.
    grace_entered_at = models.DateField(null=True, blank=True)
    # FR-11.7 account deletion: set on request, a daily sweep anonymizes the
    # org's members 30 days later. Reuses this row rather than a one-off
    # single-purpose model.
    deletion_requested_at = models.DateField(null=True, blank=True)
    # Set once the daily sweep has anonymized this org — stops the sweep
    # from reprocessing an already-scrubbed org every day thereafter.
    anonymized_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.org_id}: {self.plan.code}/{self.status}"


class SaasInvoiceCounter(models.Model):
    """Global sequence (not per-org — these are FitKhata's own IRD invoices
    to its tenants, one shared numbering series). Mirrors
    billing.InvoiceCounter's row-locked shape minus the org FK — a literal
    singleton row, locked the same way.
    """

    fiscal_year = models.PositiveIntegerField(unique=True)
    last_value = models.PositiveIntegerField(default=0)

    def __str__(self) -> str:
        return f"{self.fiscal_year}: {self.last_value}"


class SaasInvoice(models.Model):
    """FitKhata's own invoice to a tenant org — separate counter/series from
    that org's own tenant-facing billing.Invoice (rule 8 numbering doesn't
    apply here; see SaasInvoiceCounter above for this series' own scheme).
    """

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ISSUED = "issued", "Issued"
        PAID = "paid", "Paid"
        VOID = "void", "Void"

    class Kind(models.TextChoices):
        SUBSCRIPTION = "subscription", "Subscription fee"
        # FR-11.5: a top-up reuses this same draft->issued->paid/gateway
        # round trip rather than a parallel one-off model — see
        # saas/services.py::confirm_sms_topup.
        SMS_TOPUP = "sms_topup", "SMS wallet top-up"

    org = models.ForeignKey(
        "gyms.Organization", on_delete=models.CASCADE, related_name="saas_invoices"
    )
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.SUBSCRIPTION)
    number = models.CharField(max_length=30, unique=True)
    # Only meaningful for kind=subscription (first-of-month billed period).
    period = models.DateField(null=True, blank=True)
    lines = models.JSONField(default=list)  # [{"label": ..., "amount_npr": "..."}]
    subtotal_npr = models.DecimalField(max_digits=12, decimal_places=2)
    vat_npr = models.DecimalField(max_digits=12, decimal_places=2)
    total_npr = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    paid_via = models.CharField(max_length=20, blank=True)  # esewa/khalti/bank
    # Idempotency key for the gateway initiate/verify round trip — same role
    # as billing.Payment.transaction_uuid.
    transaction_uuid = models.UUIDField(default=uuid.uuid4, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return self.number


class FeatureFlag(models.Model):
    """Ops-controlled kill-switch/beta-rollout layer — see saas/services.py
    has_feature() for how this and SaasPlan.features combine.
    """

    key = models.CharField(max_length=100, unique=True)
    default = models.BooleanField(default=False)
    # {"<org_id>": true/false} — low cardinality, admin-managed; a JSON dict
    # is simpler than a whole overrides table for this volume of data.
    per_org_overrides = models.JSONField(default=dict, blank=True)
    rollout_pct = models.PositiveSmallIntegerField(null=True, blank=True)

    def __str__(self) -> str:
        return self.key


class SupportTicket(models.Model):
    """FR-11.6."""

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"
        URGENT = "urgent", "Urgent"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        PENDING = "pending", "Pending"
        RESOLVED = "resolved", "Resolved"

    org = models.ForeignKey(
        "gyms.Organization", on_delete=models.CASCADE, related_name="support_tickets"
    )
    subject = models.CharField(max_length=200)
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.MEDIUM)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.subject


class SupportTicketMessage(models.Model):
    ticket = models.ForeignKey(SupportTicket, on_delete=models.CASCADE, related_name="messages")
    # Null author = the org's side posting without a FitKhata User row to
    # attribute to (e.g. a future non-staff submission channel) — kept
    # nullable rather than assuming every message has a platform actor.
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]


class Lead(models.Model):
    """FR-12.6: a captured trial/sales lead -- Facebook Lead Ads today,
    `source` leaves room for others later. Platform-level like everything
    else in this file: a lead precedes any Organization existing at all, so
    it can't be a TenantModel. No pipeline/stage field -- this codebase has
    no actual lead pipeline built yet (the spec's own "Phase 2 pipeline"
    reference doesn't correspond to anything in this repo); this is
    deliberately just a flat capture log for staff to work from manually.
    """

    class Status(models.TextChoices):
        NEW = "new", "New"
        CONTACTED = "contacted", "Contacted"
        CONVERTED = "converted", "Converted"
        LOST = "lost", "Lost"

    full_name = models.CharField(max_length=200, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    source = models.CharField(max_length=50, default="facebook_lead_ads")
    raw_payload = models.JSONField(default=dict)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.full_name or self.phone or self.email} ({self.source})"


class PlatformAuditLog(models.Model):
    """Cross-tenant/platform-staff action audit — core.AuditLog can't
    represent these (it requires non-null org AND gym; several of these
    actions have neither, or only an org). Append-only by convention, not a
    DB-trigger-enforced table like core.AuditLog — lower stakes, not worth a
    second trigger migration for this.
    """

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    org = models.ForeignKey(
        "gyms.Organization", on_delete=models.SET_NULL, null=True, blank=True
    )
    action = models.CharField(max_length=50)
    target_type = models.CharField(max_length=50, blank=True)
    target_id = models.CharField(max_length=64, blank=True)
    # Required by the view for impersonation; optional for everything else.
    reason = models.CharField(max_length=500, blank=True)
    before = models.JSONField(null=True, blank=True)
    after = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["org", "action"])]

    def __str__(self) -> str:
        return f"{self.action} by {self.actor_id}"
