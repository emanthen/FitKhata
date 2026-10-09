from __future__ import annotations

from django.db import models

from core.models import TenantModel


class InvoiceCounter(models.Model):
    """Org-scoped, not gym-scoped — rule 8 numbers invoices sequentially per
    org per fiscal year, not per branch. Deliberately not a TenantModel (no
    gym field): a sale at any branch of the org shares the same sequence.
    RLS for this table is org-scoped (see billing/migrations), so it's not
    picked up by tests/rls/test_isolation.py's generic gym-field
    introspection — that test only verifies gym-scoped tables.
    """

    org = models.ForeignKey("gyms.Organization", on_delete=models.CASCADE)
    fiscal_year = models.PositiveIntegerField()
    last_value = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["org", "fiscal_year"], name="unique_org_fiscal_year_counter"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.org_id}/{self.fiscal_year}: {self.last_value}"


class Invoice(TenantModel):
    """sell_membership() creates these as status=draft with lines — a draft
    invoice IS the "member owes money" signal attendance/services.py's
    member_dues_npr() and the gate's classify_checkin already rely on, so
    that path is unchanged by Phase 4. billing.services.collect_payment()
    is what transitions draft -> issued once a Payment settles it (rule 6);
    void is for corrections (rule 8 — never delete a numbered invoice).
    """

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ISSUED = "issued", "Issued"
        VOID = "void", "Void"

    number = models.CharField(max_length=30)
    fiscal_year = models.PositiveIntegerField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    member = models.ForeignKey(
        "members.Member", on_delete=models.PROTECT, related_name="invoices"
    )
    subtotal_npr = models.DecimalField(max_digits=12, decimal_places=2)
    discount_npr = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    taxable_npr = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    vat_npr = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_npr = models.DecimalField(max_digits=12, decimal_places=2)
    # IRD invoice fields (FR-4.x). bill_date is set once at creation and
    # never changes afterward — rule 7, invoices aren't edited in place.
    bill_date = models.DateField(null=True, blank=True)
    bill_date_bs = models.CharField(max_length=10, blank=True)  # "YYYY-MM-DD" in BS
    buyer_name = models.CharField(max_length=200, blank=True)
    buyer_pan = models.CharField(max_length=20, blank=True)
    void_reason = models.CharField(max_length=255, blank=True)
    # Nepal's Central Billing Monitoring System sync marker — not wired up
    # this phase (no CBMS integration built yet), just the column IRD
    # compliance will eventually need; null means "not yet synced".
    cbms_synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["org", "number"], name="unique_org_invoice_number"),
        ]

    def __str__(self) -> str:
        return self.number


class InvoiceLine(TenantModel):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="lines")
    description = models.CharField(max_length=200)
    quantity = models.PositiveIntegerField(default=1)
    unit_price_npr = models.DecimalField(max_digits=12, decimal_places=2)
    line_total_npr = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self) -> str:
        return f"{self.invoice_id}: {self.description}"


class GatewayCredential(TenantModel):
    """Per-gym merchant credentials — FitKhata is not a payment aggregator,
    each gym has its own eSewa/Khalti/Fonepay merchant account.
    secret_encrypted is Fernet ciphertext (core.crypto), the exact same
    pattern as Member.qr_secret — FIELD_ENCRYPTION_KEY already exists in
    settings specifically for this (see its own comment in base.py).
    """

    class Provider(models.TextChoices):
        ESEWA = "esewa", "eSewa"
        KHALTI = "khalti", "Khalti"
        FONEPAY = "fonepay", "Fonepay"

    class Environment(models.TextChoices):
        SANDBOX = "sandbox", "Sandbox"
        LIVE = "live", "Live"

    provider = models.CharField(max_length=20, choices=Provider.choices)
    environment = models.CharField(
        max_length=20, choices=Environment.choices, default=Environment.SANDBOX
    )
    merchant_code = models.CharField(max_length=100)
    secret_encrypted = models.BinaryField(editable=False)
    # Non-secret, provider-specific fields that don't fit eSewa/Khalti's
    # plain merchant_code+secret shape — currently just Fonepay's
    # "username" (its password and HMAC key, both sensitive, live inside
    # secret_encrypted as JSON instead — see billing/gateways/fonepay.py).
    extra = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["gym", "provider", "environment"],
                name="unique_gym_provider_environment",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.gym_id}:{self.provider}:{self.environment}"


class CashShift(TenantModel):
    """expected_cash_npr/variance_npr are deliberately NOT columns here —
    see billing/domain/shift.py — a Postgres generated column can't
    reference another table's rows (expected cash needs a sum over this
    shift's Payment rows), so they're computed in billing/services.py.
    """

    staff = models.ForeignKey(
        "accounts.User", on_delete=models.PROTECT, related_name="cash_shifts"
    )
    opened_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    opening_float_npr = models.DecimalField(max_digits=12, decimal_places=2)
    counted_cash_npr = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    denominations = models.JSONField(default=dict, blank=True)

    def __str__(self) -> str:
        return f"shift {self.pk} ({self.staff_id})"


class Payment(TenantModel):
    """Rule 6: confirmation is server-side only and idempotent on
    transaction_uuid (unique constraint + select_for_update in
    billing.services.collect_payment — not enforced here, this is just the
    schema-level half of that guarantee). Rule 7: never edited in place
    outside collect_payment, which always writes an AuditLog.
    """

    class Mode(models.TextChoices):
        ESEWA = "esewa", "eSewa"
        KHALTI = "khalti", "Khalti"
        FONEPAY = "fonepay", "Fonepay"
        CASH = "cash", "Cash"
        MANUAL_ESEWA = "manual_esewa", "Manual eSewa"
        BANK = "bank", "Bank transfer"
        CHEQUE = "cheque", "Cheque"

    class Channel(models.TextChoices):
        ONLINE = "online", "Online"
        DESK = "desk", "Desk"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        REFUNDED = "refunded", "Refunded"

    member = models.ForeignKey(
        "members.Member", on_delete=models.PROTECT, related_name="payments"
    )
    invoice = models.ForeignKey(
        Invoice, on_delete=models.SET_NULL, null=True, blank=True, related_name="payments"
    )
    shift = models.ForeignKey(
        CashShift, on_delete=models.SET_NULL, null=True, blank=True, related_name="payments"
    )
    mode = models.CharField(max_length=20, choices=Mode.choices)
    channel = models.CharField(max_length=20, choices=Channel.choices)
    transaction_uuid = models.UUIDField(unique=True)
    gateway_ref = models.CharField(max_length=100, blank=True)
    amount_npr = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    receipt_no = models.CharField(max_length=30, blank=True)
    # The gateway's raw callback/lookup payload, for audit/debugging.
    raw_response = models.JSONField(null=True, blank=True)
    # What this payment is FOR, when it was initiated before anything else
    # existed to link it to — e.g. an online renewal's {plan_id, promo_code,
    # addon_ids}, read by members.services.fulfill_renewal_payment once
    # collect_payment() marks this completed. Empty for desk payments
    # against an invoice that (via sell_membership) already has everything
    # it needs.
    metadata = models.JSONField(default=dict, blank=True)
    collected_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    def __str__(self) -> str:
        return f"{self.transaction_uuid} ({self.status})"


class CreditNote(TenantModel):
    """approved_by is null until an owner approves it (FR-4.8) — the first
    use of the IsOwner permission in this codebase for an actual gate
    rather than a plain role check.
    """

    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name="credit_notes")
    amount_npr = models.DecimalField(max_digits=12, decimal_places=2)
    reason = models.CharField(max_length=255)
    approved_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    approved_at = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return f"CN {self.pk} for invoice {self.invoice_id}"
