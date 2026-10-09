from __future__ import annotations

from django.contrib.postgres.fields import ArrayField
from django.contrib.postgres.indexes import GinIndex
from django.db import models

from accounts.models import phone_validator
from core.models import TenantModel


def member_photo_path(instance: Member, filename: str) -> str:
    return f"members/{instance.gym_id}/{instance.pk}/photo/{filename}"


def waiver_pdf_path(instance: Waiver, filename: str) -> str:
    return f"members/{instance.gym_id}/{instance.member_id}/waivers/{filename}"


def import_error_report_path(instance: ImportJob, filename: str) -> str:
    return f"members/{instance.gym_id}/imports/{instance.pk}/{filename}"


class MemberCodeCounter(TenantModel):
    """One row per gym — select_for_update()'d inside register_member() to
    allocate the next member_code (e.g. 'FK-0001') without gaps or races.
    """

    last_value = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["gym"], name="unique_gym_member_code_counter"),
        ]

    def __str__(self) -> str:
        return f"{self.gym_id}: {self.last_value}"


class Member(TenantModel):
    class Gender(models.TextChoices):
        MALE = "male", "Male"
        FEMALE = "female", "Female"
        OTHER = "other", "Other"

    class Language(models.TextChoices):
        NEPALI = "ne", "Nepali"
        ENGLISH = "en", "English"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        EXPIRED = "expired", "Expired"
        FROZEN = "frozen", "Frozen"
        CANCELLED = "cancelled", "Cancelled"
        TRIAL = "trial", "Trial"

    class RiskState(models.TextChoices):
        NORMAL = "normal", "Normal"
        WARNING = "warning", "Warning"
        RED_LIST = "red_list", "Red list"

    member_code = models.CharField(max_length=20)
    full_name = models.CharField(max_length=200)
    phone = models.CharField(max_length=20, validators=[phone_validator])
    email = models.EmailField(blank=True)
    gender = models.CharField(max_length=10, choices=Gender.choices, blank=True)
    dob = models.DateField(null=True, blank=True)
    emergency_contact = models.JSONField(default=dict, blank=True)
    photo = models.ImageField(upload_to=member_photo_path, blank=True, null=True)
    tags = ArrayField(models.CharField(max_length=50), default=list, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.TRIAL)
    risk_state = models.CharField(
        max_length=20, choices=RiskState.choices, default=RiskState.NORMAL
    )
    churn_score = models.FloatField(default=0.0)
    last_check_in_at = models.DateTimeField(null=True, blank=True)
    # Fernet ciphertext (core.crypto). Decrypted server-side for the gate
    # snapshot (re-encrypted per-device with AES-GCM) and for the member's
    # own pass-link redemption — see attendance app.
    qr_secret = models.BinaryField(editable=False)
    # Printed/RFID card fallback (FR-3.7) — a gate HID listener resolves a
    # scanned card UID to a member the same way it resolves member_code.
    card_uid = models.CharField(max_length=64, blank=True)
    marketing_opt_in = models.BooleanField(default=False)
    # Distinct from marketing_opt_in (campaign-only, FR-5 winback): this
    # blocks every notifications.notify() call, transactional included —
    # see notifications/services.py.
    notifications_opt_out = models.BooleanField(default=False)
    language = models.CharField(max_length=5, choices=Language.choices, default=Language.NEPALI)
    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="member_profiles",
    )
    # FR-8.8: the referral code IS member_code (no separate code-generation
    # system) -- staff enters this at registration (recited by the member),
    # since no member self-registration flow exists to capture it otherwise.
    referred_by = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="referrals",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["gym", "phone"], name="unique_gym_member_phone"),
            models.UniqueConstraint(
                fields=["gym", "member_code"], name="unique_gym_member_code"
            ),
            models.UniqueConstraint(
                fields=["gym", "card_uid"],
                name="unique_gym_card_uid",
                condition=~models.Q(card_uid=""),
            ),
        ]
        indexes = [
            GinIndex(
                fields=["full_name"], name="member_full_name_trgm", opclasses=["gin_trgm_ops"]
            ),
            GinIndex(fields=["phone"], name="member_phone_trgm", opclasses=["gin_trgm_ops"]),
            GinIndex(
                fields=["member_code"], name="member_code_trgm", opclasses=["gin_trgm_ops"]
            ),
        ]

    def __str__(self) -> str:
        return f"{self.member_code} {self.full_name}"


class Plan(TenantModel):
    name = models.CharField(max_length=100)
    duration_days = models.PositiveIntegerField()
    price_npr = models.DecimalField(max_digits=12, decimal_places=2)
    joining_fee_npr = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    access_hours = models.JSONField(default=dict, blank=True)
    pt_sessions = models.PositiveIntegerField(default=0)
    max_freeze_days = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    def __str__(self) -> str:
        return self.name


class AddOn(TenantModel):
    class Kind(models.TextChoices):
        LOCKER = "locker", "Locker"
        TOWEL = "towel", "Towel"
        PT = "pt", "Personal training"
        DIET = "diet", "Diet plan"

    name = models.CharField(max_length=100)
    price_npr = models.DecimalField(max_digits=12, decimal_places=2)
    kind = models.CharField(max_length=20, choices=Kind.choices)

    def __str__(self) -> str:
        return self.name


class PromoCode(TenantModel):
    class Kind(models.TextChoices):
        FLAT = "flat", "Flat amount"
        PERCENT = "percent", "Percent"

    code = models.CharField(max_length=30)
    kind = models.CharField(max_length=20, choices=Kind.choices)
    value = models.DecimalField(max_digits=10, decimal_places=2)
    valid_from = models.DateField()
    valid_to = models.DateField()
    usage_limit = models.PositiveIntegerField(null=True, blank=True)
    per_member_once = models.BooleanField(default=True)
    times_used = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["gym", "code"], name="unique_gym_promo_code"),
        ]

    def __str__(self) -> str:
        return self.code


class PromoCodeRedemption(TenantModel):
    """One row per (promo, member) use — lets per_member_once/usage_limit be
    checked by a real query instead of guessing from invoice text.
    """

    promo = models.ForeignKey(PromoCode, on_delete=models.CASCADE, related_name="redemptions")
    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name="promo_redemptions")

    def __str__(self) -> str:
        return f"{self.promo_id}:{self.member_id}"


class Membership(TenantModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        EXPIRED = "expired", "Expired"
        PAUSED = "paused", "Paused"
        CANCELLED = "cancelled", "Cancelled"

    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name="memberships")
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name="memberships")
    start_date = models.DateField()
    expiry_date = models.DateField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    invoice = models.ForeignKey(
        "billing.Invoice",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="memberships",
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(expiry_date__gte=models.F("start_date")),
                name="membership_expiry_gte_start",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.member_id}: {self.start_date}..{self.expiry_date}"


class Waiver(TenantModel):
    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name="waivers")
    signed_pdf = models.FileField(upload_to=waiver_pdf_path)
    signed_at = models.DateTimeField(auto_now_add=True)
    ip = models.GenericIPAddressField(null=True, blank=True)

    def __str__(self) -> str:
        return f"waiver:{self.member_id}:{self.signed_at:%Y-%m-%d}"


class MemberFeedback(TenantModel):
    """FR-8.6: a member-submitted complaint/feedback, routed to the branch
    manager by members.services.submit_feedback -- gym-wide and member-
    initiated, not specific to coaching or retention's domains.
    """

    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name="feedback")
    message = models.TextField(max_length=1000)

    def __str__(self) -> str:
        return f"feedback:{self.member_id}:{self.created_at:%Y-%m-%d}"


class ImportJob(TenantModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        DONE = "done", "Done"
        FAILED = "failed", "Failed"

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    total_rows = models.PositiveIntegerField(default=0)
    success_count = models.PositiveIntegerField(default=0)
    error_report = models.FileField(upload_to=import_error_report_path, blank=True, null=True)
    uploaded_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True
    )

    def __str__(self) -> str:
        return f"import {self.pk} ({self.status})"
