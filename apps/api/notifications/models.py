from __future__ import annotations

from django.db import models

from core.models import TenantModel


class Template(models.Model):
    """Platform-wide message catalog — NOT a TenantModel. org is nullable:
    a NULL row is a platform default (seeded once, migrations/0003), an
    org-set row is that org's own override of the same (key, channel,
    language) — resolve_template() in services.py prefers the override.
    Same "specific row beats a broader default" shape as billing's
    GatewayCredential (live preferred over sandbox).
    """

    class Key(models.TextChoices):
        WELCOME = "welcome", "Welcome"
        PAYMENT_RECEIPT = "payment_receipt", "Payment receipt"
        EXPIRY_7D = "expiry_7d", "Expiry 7d"
        EXPIRY_3D = "expiry_3d", "Expiry 3d"
        EXPIRY_1D = "expiry_1d", "Expiry 1d"
        EXPIRED_1D = "expired_1d", "Expired 1d"
        EXPIRED_7D = "expired_7d", "Expired 7d"
        BIRTHDAY = "birthday", "Birthday"
        RED_LIST_DAY7 = "red_list_day7", "Red list day 7"
        RED_LIST_DAY10 = "red_list_day10", "Red list day 10"
        FREEZE_APPLIED = "freeze_applied", "Freeze applied"
        CLASS_BOOKED = "class_booked", "Class booked"
        WINBACK = "winback", "Winback"
        # Phase 7 (coaching) additions — notify() call sites in
        # coaching/services.py's approve_coaching_report/cancel_booking.
        COACHING_REPORT_READY = "coaching_report_ready", "Coaching report ready"
        CLASS_BOOKING_PROMOTED = "class_booking_promoted", "Class booking promoted"

    class Channel(models.TextChoices):
        SMS = "sms", "SMS"
        WHATSAPP = "whatsapp", "WhatsApp"
        PUSH = "push", "Push"
        EMAIL = "email", "Email"

    class Language(models.TextChoices):
        NE = "ne", "Nepali"
        EN = "en", "English"

    org = models.ForeignKey(
        "gyms.Organization", on_delete=models.CASCADE, null=True, blank=True, related_name="+"
    )
    key = models.CharField(max_length=30, choices=Key.choices)
    channel = models.CharField(max_length=20, choices=Channel.choices)
    language = models.CharField(max_length=5, choices=Language.choices)
    body = models.TextField()
    # Meta requires a pre-approved template name for WhatsApp sends — blank
    # for channels/keys that don't have one (see migrations/0003's seed set).
    whatsapp_template_name = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["org", "key", "channel", "language"], name="unique_template_scope"
            ),
        ]

    def __str__(self) -> str:
        scope = f"org:{self.org_id}" if self.org_id else "default"
        return f"{self.key}/{self.channel}/{self.language} ({scope})"


class Notification(TenantModel):
    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        SENT = "sent", "Sent"
        DELIVERED = "delivered", "Delivered"
        FAILED = "failed", "Failed"

    member = models.ForeignKey(
        "members.Member", on_delete=models.CASCADE, related_name="notifications"
    )
    channel = models.CharField(max_length=20, choices=Template.Channel.choices)
    # "" for an ad-hoc broadcast send (no single Template row drives it —
    # Broadcast carries its own body_ne/body_en instead).
    template_key = models.CharField(max_length=30, blank=True)
    language = models.CharField(max_length=5, choices=Template.Language.choices)
    # {"body": <rendered text>, "context": {...}, "whatsapp_template_name"?: str}
    payload = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.QUEUED)
    attempt_count = models.PositiveIntegerField(default=0)
    provider_ref = models.CharField(max_length=150, blank=True)
    cost_npr = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    error = models.TextField(blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    # Set when this row exists because an earlier attempt on a different
    # channel dead-ended (domain/retry.py's "fallback" action) — lets the
    # delivery log show the whole chain for one logical notification.
    fallback_of = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="fallbacks"
    )

    class Meta:
        indexes = [
            models.Index(fields=["gym", "member", "created_at"]),
            models.Index(fields=["gym", "status"]),
        ]

    def __str__(self) -> str:
        return f"{self.member_id}: {self.channel}/{self.template_key} ({self.status})"


class SmsWallet(models.Model):
    """One per Organization, not a TenantModel — SMS cost is billed to the
    org as a whole (FR-11.5), the same reasoning as billing.InvoiceCounter
    being org-scoped rather than per-branch. Carries an org-scoped RLS
    policy (core/migrations/0004_platform_org_rls.py) as a backstop, same
    as saas/models.py's platform tables — query it under
    core.context.system_context() as the primary mechanism, not this.
    """

    org = models.OneToOneField(
        "gyms.Organization", on_delete=models.CASCADE, related_name="sms_wallet"
    )
    balance_npr = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.org_id}: NPR {self.balance_npr}"


class SmsWalletTx(models.Model):
    class Reason(models.TextChoices):
        DEBIT = "debit", "Debit"
        TOPUP = "topup", "Top-up"
        ADJUSTMENT = "adjustment", "Adjustment"

    wallet = models.ForeignKey(SmsWallet, on_delete=models.CASCADE, related_name="transactions")
    amount_npr = models.DecimalField(max_digits=12, decimal_places=2)  # negative = debit
    reason = models.CharField(max_length=20, choices=Reason.choices)
    notification = models.ForeignKey(
        Notification, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.wallet_id}: {self.amount_npr} ({self.reason})"


class PushSubscription(TenantModel):
    member = models.ForeignKey(
        "members.Member", on_delete=models.CASCADE, related_name="push_subscriptions"
    )
    endpoint = models.URLField(max_length=500, unique=True)
    keys = models.JSONField()  # {"p256dh": ..., "auth": ...}
    user_agent = models.CharField(max_length=255, blank=True)
    last_seen_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.member_id}: {self.endpoint[:40]}"


class Broadcast(TenantModel):
    """FR-6.4: send == create (there's no separate draft state, matching
    retention.Campaign's shape) — estimate_broadcast() is a read-only
    preview computed before this row ever exists.
    """

    class Segment(models.TextChoices):
        EXPIRED = "expired", "Expired"
        RED_LIST = "red_list", "Red list"
        PLAN = "plan", "Plan"
        GENDER = "gender", "Gender"
        TAG = "tag", "Tag"

    segment = models.CharField(max_length=20, choices=Segment.choices)
    segment_value = models.CharField(max_length=100, blank=True)
    channel = models.CharField(max_length=20, choices=Template.Channel.choices)
    body_ne = models.TextField()
    body_en = models.TextField()
    recipient_count = models.PositiveIntegerField(default=0)
    cost_npr = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True
    )
    sent_at = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return f"{self.segment}:{self.segment_value} ({self.recipient_count} recipients)"


class Announcement(TenantModel):
    """FR-6.7: a gym-wide banner in the Member PWA — not per-member fan-out,
    so there's no Notification row per viewer and no server-side read
    tracking (YAGNI; the PWA can dismiss locally if ever needed).
    """

    title = models.CharField(max_length=200)
    body_ne = models.TextField()
    body_en = models.TextField()
    is_active = models.BooleanField(default=True)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True
    )

    def __str__(self) -> str:
        return self.title
