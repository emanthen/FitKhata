from __future__ import annotations

import uuid

from django.db import models

from coaching.storage import get_private_media_storage
from core.models import TenantModel


class ClientProfile(TenantModel):
    class Goal(models.TextChoices):
        WEIGHT_LOSS = "weight_loss", "Weight loss"
        WEIGHT_GAIN = "weight_gain", "Weight gain"
        MUSCLE_GAIN = "muscle_gain", "Muscle gain"
        GENERAL_FITNESS = "general_fitness", "General fitness"
        ENDURANCE = "endurance", "Endurance"

    member = models.OneToOneField(
        "members.Member", on_delete=models.CASCADE, related_name="coaching_profile"
    )
    trainer = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="coaching_clients",
    )
    primary_goal = models.CharField(max_length=20, choices=Goal.choices)
    starting_weight_kg = models.DecimalField(max_digits=5, decimal_places=2)
    target_weight_kg = models.DecimalField(max_digits=5, decimal_places=2)
    workout_plan = models.ForeignKey(
        "coaching.WorkoutPlan", on_delete=models.SET_NULL, null=True, blank=True
    )
    diet_plan = models.ForeignKey(
        "coaching.DietPlan", on_delete=models.SET_NULL, null=True, blank=True
    )
    coach_notes = models.TextField(blank=True)
    # FitKhata's AI insights are shared with the gym owner, and a trainer
    # must approve before a member sees anything — but sending a member's
    # health data (weight, body-fat, photos) to an external LLM at all
    # still needs the member's own opt-in first. This gates notify-worthy
    # Celery enqueueing in coaching/tasks.py, not just a UI checkbox.
    consent_health_data = models.BooleanField(default=False)
    consent_at = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return f"profile:{self.member_id}"


class BodyMeasurement(TenantModel):
    member = models.ForeignKey(
        "members.Member", on_delete=models.CASCADE, related_name="measurements"
    )
    measured_on = models.DateField()
    weight_kg = models.DecimalField(max_digits=5, decimal_places=2)
    body_fat_pct = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    # Free-form extra tape-measurements, e.g. {"waist_cm": 82, "chest_cm": 101}
    measurements = models.JSONField(default=dict, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["member", "measured_on"], name="unique_member_measurement_day"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.member_id}@{self.measured_on}: {self.weight_kg}kg"


def body_measurement_photo_path(instance: BodyMeasurementPhoto, filename: str) -> str:
    return f"coaching/{instance.gym_id}/{instance.measurement_id}/{filename}"


class BodyMeasurementPhoto(TenantModel):
    """One row per photo (not a JSONField of paths) — each gets its own
    freshly-generated 5-minute signed URL at serialize time (never stored),
    see coaching/storage.py::PrivateMediaStorage.
    """

    class Angle(models.TextChoices):
        FRONT = "front", "Front"
        SIDE = "side", "Side"
        BACK = "back", "Back"

    measurement = models.ForeignKey(
        BodyMeasurement, on_delete=models.CASCADE, related_name="photos"
    )
    image = models.ImageField(
        upload_to=body_measurement_photo_path, storage=get_private_media_storage
    )
    angle = models.CharField(max_length=10, choices=Angle.choices, blank=True)

    def __str__(self) -> str:
        return f"photo:{self.measurement_id}:{self.angle}"


class Exercise(models.Model):
    """Global catalog — not a TenantModel, same shape as notifications.Template's
    platform-default rows: every gym shares one exercise library.
    """

    class MuscleGroup(models.TextChoices):
        CHEST = "chest", "Chest"
        BACK = "back", "Back"
        SHOULDERS = "shoulders", "Shoulders"
        BICEPS = "biceps", "Biceps"
        TRICEPS = "triceps", "Triceps"
        LEGS = "legs", "Legs"
        GLUTES = "glutes", "Glutes"
        CORE = "core", "Core"
        CARDIO = "cardio", "Cardio"

    class Equipment(models.TextChoices):
        BARBELL = "barbell", "Barbell"
        DUMBBELL = "dumbbell", "Dumbbell"
        MACHINE = "machine", "Machine"
        BODYWEIGHT = "bodyweight", "Bodyweight"
        CABLE = "cable", "Cable"
        BAND = "band", "Band"
        KETTLEBELL = "kettlebell", "Kettlebell"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name_en = models.CharField(max_length=150)
    name_ne = models.CharField(max_length=150)
    muscle_group = models.CharField(max_length=20, choices=MuscleGroup.choices)
    equipment = models.CharField(max_length=20, choices=Equipment.choices)
    media_url = models.URLField(blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self) -> str:
        return self.name_en


class WorkoutPlan(TenantModel):
    class Split(models.TextChoices):
        PPL = "ppl", "Push/Pull/Legs"
        UPPER_LOWER = "upper_lower", "Upper/Lower"
        FULL_BODY = "full_body", "Full body"
        CUSTOM = "custom", "Custom"

    name = models.CharField(max_length=150)
    split = models.CharField(max_length=20, choices=Split.choices)
    # [{"day": "mon", "exercises": [{"exercise_id": "<uuid>", "sets": 3,
    #   "reps": 10, "rest_s": 60}]}]
    days = models.JSONField(default=list, blank=True)
    created_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True
    )

    def __str__(self) -> str:
        return self.name


class WorkoutLog(TenantModel):
    member = models.ForeignKey(
        "members.Member", on_delete=models.CASCADE, related_name="workout_logs"
    )
    logged_on = models.DateField()
    exercise = models.ForeignKey(Exercise, on_delete=models.PROTECT)
    sets = models.JSONField(default=list, blank=True)  # [{"kg": 60, "reps": 8}, ...]

    class Meta:
        indexes = [models.Index(fields=["gym", "member", "logged_on"])]

    def __str__(self) -> str:
        return f"{self.member_id}@{self.logged_on}: {self.exercise_id}"


class DietLog(TenantModel):
    """Daily protein intake — not in the FR's literal model list, but
    coaching/domain/flags.py's low_protein flag and progress.py's
    macro_pct formula both need *some* real per-day record to operate on,
    and nothing else in this phase provides one (the FR's diet feature is
    plan *building*, not meal-by-meal food logging). Kept minimal: one
    number a trainer or member can enter per day, not a full per-meal log.
    """

    member = models.ForeignKey("members.Member", on_delete=models.CASCADE, related_name="diet_logs")
    logged_on = models.DateField()
    protein_g = models.DecimalField(max_digits=6, decimal_places=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["member", "logged_on"], name="unique_member_diet_log_day"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.member_id}@{self.logged_on}: {self.protein_g}g protein"


class FoodItem(models.Model):
    """Global catalog, same reasoning as Exercise."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name_en = models.CharField(max_length=100)
    name_ne = models.CharField(max_length=100)
    kcal_per_100g = models.DecimalField(max_digits=6, decimal_places=1)
    protein_g_per_100g = models.DecimalField(max_digits=5, decimal_places=1)
    carbs_g_per_100g = models.DecimalField(max_digits=5, decimal_places=1)
    fat_g_per_100g = models.DecimalField(max_digits=5, decimal_places=1)

    def __str__(self) -> str:
        return self.name_en


class DietPlan(TenantModel):
    """Seeded per-gym at gym-creation time (coaching.services.seed_default_diet_plans),
    not via migration — see that function's docstring for why (no Gym row
    exists at migration time, and RLS would hide a nullable-gym row anyway).
    """

    name = models.CharField(max_length=150)
    kcal_target = models.PositiveIntegerField()
    protein_g = models.DecimalField(max_digits=5, decimal_places=1)
    # [{"meal": "breakfast", "items": [{"food_item_id": "<uuid>", "grams": 150}]}]
    meals = models.JSONField(default=list, blank=True)
    created_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True
    )

    def __str__(self) -> str:
        return self.name


class PTPack(TenantModel):
    member = models.ForeignKey("members.Member", on_delete=models.CASCADE, related_name="pt_packs")
    trainer = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True)
    sessions_total = models.PositiveIntegerField()
    sessions_used = models.PositiveIntegerField(default=0)
    # Not in the FR's literal field list — added because TrainerCommission
    # needs an amount basis to compute from.
    price_npr = models.DecimalField(max_digits=12, decimal_places=2)
    expires_on = models.DateField()

    def __str__(self) -> str:
        return f"pack:{self.member_id} ({self.sessions_used}/{self.sessions_total})"


class PTSession(TenantModel):
    pack = models.ForeignKey(PTPack, on_delete=models.CASCADE, related_name="sessions")
    scheduled_at = models.DateTimeField()
    attended = models.BooleanField(default=False)

    def __str__(self) -> str:
        return f"session:{self.pack_id}@{self.scheduled_at}"


class ClassSchedule(TenantModel):
    name = models.CharField(max_length=150)
    trainer = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True)
    starts_at = models.DateTimeField()
    capacity = models.PositiveIntegerField()

    def __str__(self) -> str:
        return f"{self.name}@{self.starts_at}"


class ClassBooking(TenantModel):
    class Status(models.TextChoices):
        BOOKED = "booked", "Booked"
        WAITLIST = "waitlist", "Waitlist"
        CANCELLED = "cancelled", "Cancelled"
        ATTENDED = "attended", "Attended"

    class_schedule = models.ForeignKey(
        ClassSchedule, on_delete=models.CASCADE, related_name="bookings"
    )
    member = models.ForeignKey(
        "members.Member", on_delete=models.CASCADE, related_name="class_bookings"
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.BOOKED)

    class Meta:
        constraints = [
            # Allows rebooking after a cancel: only one non-cancelled row
            # per (class, member) at a time, not a lifetime-unique pair.
            models.UniqueConstraint(
                fields=["class_schedule", "member"],
                condition=~models.Q(status="cancelled"),
                name="unique_active_booking_per_member",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.member_id}@{self.class_schedule_id} ({self.status})"


class TrainerCommission(TenantModel):
    """FR-7's own note: "feeds Phase 9" — this phase only writes correct
    rows, a future staff/payroll phase is what reads and pays them out.
    """

    class Source(models.TextChoices):
        PT_SESSION = "pt_session", "PT session"
        PT_PACK = "pt_pack", "PT pack"

    trainer = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True)
    source = models.CharField(max_length=20, choices=Source.choices)
    amount_npr = models.DecimalField(max_digits=12, decimal_places=2)
    period = models.CharField(max_length=7)  # "2026-10"
    pt_session = models.ForeignKey(
        PTSession, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    pt_pack = models.ForeignKey(
        PTPack, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    def __str__(self) -> str:
        return f"{self.trainer_id}: {self.amount_npr} ({self.source}/{self.period})"


class CoachingReport(TenantModel):
    class Kind(models.TextChoices):
        MEMBER = "member", "Member"
        BRANCH = "branch", "Branch"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    member = models.ForeignKey(
        "members.Member",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="coaching_reports",
    )
    week_start = models.DateField()
    kind = models.CharField(max_length=10, choices=Kind.choices)
    flags = models.JSONField(default=list, blank=True)
    suggestions = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    approved_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    # Blank = rules-only fallback, no LLM call actually happened this week.
    model = models.CharField(max_length=50, blank=True)
    tokens_used = models.PositiveIntegerField(default=0)
    cost_npr = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["gym", "member", "week_start", "kind"], name="unique_member_coaching_report"
            ),
            models.UniqueConstraint(
                fields=["gym", "week_start"],
                condition=models.Q(kind="branch"),
                name="unique_branch_coaching_report_per_week",
            ),
        ]

    def __str__(self) -> str:
        return f"report:{self.kind}:{self.member_id or 'branch'}@{self.week_start}"
