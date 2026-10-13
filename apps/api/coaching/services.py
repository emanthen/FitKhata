"""Business logic for client profiles, measurements, logging, diet-plan
seeding, bookings/waitlist, PT attendance, and report review. Rule 9: views
stay thin, this is where it lives.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.utils import timezone

from coaching.domain.diet import FoodItemMacros, MealItem, meal_plan_totals
from coaching.models import (
    BodyMeasurement,
    BodyMeasurementPhoto,
    ClassBooking,
    ClassSchedule,
    ClientProfile,
    CoachingReport,
    DietLog,
    DietPlan,
    FoodItem,
    PTPack,
    PTSession,
    TrainerCommission,
    WorkoutLog,
)
from core.services import audit
from core.validators import strip_exif, validate_image_file
from notifications.services import notify

# Assumed baseline for attendance_pct/low_attendance when no per-member
# target exists — not configurable per gym this phase, same "pick one
# sensible default, document it" spirit as retention's DEFAULT_WARNING_DAYS.
EXPECTED_VISITS_PER_WEEK = 3


class MaxCapacityReached(ValueError):
    pass


class AlreadyBooked(ValueError):
    pass


def create_client_profile(
    member: Any,
    trainer: Any,
    primary_goal: str,
    starting_weight_kg: Decimal,
    target_weight_kg: Decimal,
    actor: Any = None,
) -> ClientProfile:
    profile = ClientProfile.objects.create(
        org=member.org,
        gym=member.gym,
        member=member,
        trainer=trainer,
        primary_goal=primary_goal,
        starting_weight_kg=starting_weight_kg,
        target_weight_kg=target_weight_kg,
    )
    audit(profile, "create", after={"primary_goal": primary_goal}, actor=actor)
    return profile


def set_health_data_consent(
    profile: ClientProfile, consented: bool, actor: Any = None
) -> ClientProfile:
    """The member's own opt-in before any of their health data is ever sent
    to an external LLM — separate from the trainer-managed fields on this
    same profile.
    """
    profile.consent_health_data = consented
    profile.consent_at = timezone.now() if consented else None
    profile.save(update_fields=["consent_health_data", "consent_at"])
    audit(profile, "update", after={"consent_health_data": consented}, actor=actor)
    return profile


def record_measurement(
    member: Any,
    measured_on: date,
    weight_kg: Decimal,
    body_fat_pct: Decimal | None = None,
    measurements: dict | None = None,
    photos: list[tuple[Any, str]] | None = None,
    actor: Any = None,
) -> BodyMeasurement:
    """`photos` is a list of (uploaded_file, angle) pairs — one
    BodyMeasurementPhoto row per photo, each independently signed-URL-able.
    """
    with transaction.atomic():
        measurement, _created = BodyMeasurement.objects.update_or_create(
            member=member,
            measured_on=measured_on,
            defaults={
                "org": member.org,
                "gym": member.gym,
                "weight_kg": weight_kg,
                "body_fat_pct": body_fat_pct,
                "measurements": measurements or {},
            },
        )
        for uploaded_file, angle in photos or []:
            validate_image_file(uploaded_file)
            BodyMeasurementPhoto.objects.create(
                org=member.org,
                gym=member.gym,
                measurement=measurement,
                image=strip_exif(uploaded_file),
                angle=angle,
            )
    audit(measurement, "update", after={"weight_kg": str(weight_kg)}, actor=actor)
    return measurement


def log_workout(
    member: Any, logged_on: date, exercise: Any, sets: list[dict], actor: Any = None
) -> WorkoutLog:
    """The <=3-tap quick logger: pick an exercise, confirm sets/reps
    (prefilled from the member's last log for that exercise by the caller),
    save — no other required input.
    """
    log = WorkoutLog.objects.create(
        org=member.org,
        gym=member.gym,
        member=member,
        logged_on=logged_on,
        exercise=exercise,
        sets=sets,
    )
    return log


def log_protein_intake(
    member: Any, logged_on: date, protein_g: Decimal, actor: Any = None
) -> DietLog:
    entry, _created = DietLog.objects.update_or_create(
        member=member,
        logged_on=logged_on,
        defaults={"org": member.org, "gym": member.gym, "protein_g": protein_g},
    )
    return entry


# --- Diet plan seeding (judgment call 7) -------------------------------------


def _meals_and_targets(items: list[tuple[str, float]]) -> tuple[list[dict], int, Decimal]:
    """items = [(food_item name_en, grams), ...] for one single-meal template.
    Looks up each FoodItem by name, computes actual totals via
    meal_plan_totals, and uses those as the seeded plan's own target —
    these are example templates a trainer can edit, not fixed prescriptions.
    """
    food_items_by_name = {
        f.name_en: f for f in FoodItem.objects.filter(name_en__in=[n for n, _ in items])
    }
    meal_items = []
    macros_by_id: dict[str, FoodItemMacros] = {}
    for name, grams in items:
        food_item = food_items_by_name.get(name)
        if food_item is None:
            continue
        meal_items.append(MealItem(food_item_id=str(food_item.pk), grams=grams))
        macros_by_id[str(food_item.pk)] = FoodItemMacros(
            kcal_per_100g=float(food_item.kcal_per_100g),
            protein_g_per_100g=float(food_item.protein_g_per_100g),
            carbs_g_per_100g=float(food_item.carbs_g_per_100g),
            fat_g_per_100g=float(food_item.fat_g_per_100g),
        )
    totals = meal_plan_totals([meal_items], macros_by_id)
    meals_json = [
        {
            "meal": "main",
            "items": [{"food_item_id": mi.food_item_id, "grams": mi.grams} for mi in meal_items],
        }
    ]
    return meals_json, round(totals.kcal), Decimal(str(round(totals.protein_g, 1)))


# name, [(FoodItem.name_en, grams), ...]
_DIET_TEMPLATES: list[tuple[str, list[tuple[str, float]]]] = [
    (
        "Dal-Bhat Standard",
        [
            ("Rice (bhat)", 250),
            ("Lentils (dal)", 150),
            ("Mixed vegetable curry (tarkari)", 150),
            ("Egg (whole, boiled)", 50),
        ],
    ),
    (
        "Roti-Tarkari",
        [
            ("Roti (whole wheat)", 200),
            ("Mixed vegetable curry (tarkari)", 200),
            ("Plain yogurt (dahi)", 100),
        ],
    ),
    (
        "Chana Protein Bowl",
        [("Chickpeas (chana)", 150), ("Rice (bhat)", 150), ("Plain yogurt (dahi)", 100)],
    ),
    (
        "Paneer High-Protein",
        [("Paneer", 150), ("Rice (bhat)", 150), ("Mixed vegetable curry (tarkari)", 100)],
    ),
    (
        "Egg & Roti",
        [("Egg (whole, boiled)", 150), ("Roti (whole wheat)", 100), ("Milk (whole)", 200)],
    ),
    (
        "Chicken & Rice",
        [
            ("Chicken breast (cooked)", 200),
            ("Rice (bhat)", 200),
            ("Mixed vegetable curry (tarkari)", 100),
        ],
    ),
    (
        "Sel Roti Festival Treat",
        [("Sel roti", 150), ("Plain yogurt (dahi)", 100), ("Milk (whole)", 100)],
    ),
]


def seed_default_diet_plans(gym: Any) -> list[DietPlan]:
    """Called from gyms.views.GymCreateView.post right after a Gym is
    created — NOT a migration: DietPlan is a TenantModel (no Gym row exists
    yet at migration time, and a nullable gym would make RLS hide the row
    from every tenant). NOT seed_demo.py either — these 7 Nepali templates
    are real, must-exist-for-every-gym catalog content, not dev fixture data.
    """
    plans = []
    for name, items in _DIET_TEMPLATES:
        meals_json, kcal_target, protein_g = _meals_and_targets(items)
        plans.append(
            DietPlan.objects.create(
                org=gym.org,
                gym=gym,
                name=name,
                kcal_target=kcal_target,
                protein_g=protein_g,
                meals=meals_json,
            )
        )
    return plans


# --- Coaching report review ("trainer approves before a member sees anything") --


def approve_coaching_report(report: CoachingReport, actor: Any) -> CoachingReport:
    report.status = CoachingReport.Status.APPROVED
    report.approved_by = actor
    report.approved_at = timezone.now()
    report.save(update_fields=["status", "approved_by", "approved_at"])
    audit(report, "update", after={"status": "approved"}, actor=actor)
    if report.kind == CoachingReport.Kind.MEMBER and report.member is not None:
        notify(report.member, "coaching_report_ready", {"name": report.member.full_name})
    return report


def reject_coaching_report(report: CoachingReport, actor: Any, reason: str = "") -> CoachingReport:
    report.status = CoachingReport.Status.REJECTED
    report.save(update_fields=["status"])
    audit(
        report,
        "update",
        before={"status": "draft"},
        after={"status": "rejected", "reason": reason},
        actor=actor,
    )
    return report


# --- Classes: booking + waitlist auto-promote (FR-7.10) ----------------------


def book_class(schedule: ClassSchedule, member: Any, actor: Any = None) -> ClassBooking:
    with transaction.atomic():
        locked_schedule = ClassSchedule.objects.select_for_update().get(pk=schedule.pk)
        existing = (
            ClassBooking.objects.filter(class_schedule=locked_schedule, member=member)
            .exclude(status=ClassBooking.Status.CANCELLED)
            .first()
        )
        if existing is not None:
            raise AlreadyBooked("This member already has an active booking for this class.")

        booked_count = ClassBooking.objects.filter(
            class_schedule=locked_schedule, status=ClassBooking.Status.BOOKED
        ).count()
        under_capacity = booked_count < locked_schedule.capacity
        status = ClassBooking.Status.BOOKED if under_capacity else ClassBooking.Status.WAITLIST
        booking = ClassBooking.objects.create(
            org=member.org,
            gym=member.gym,
            class_schedule=locked_schedule,
            member=member,
            status=status,
        )
    audit(booking, "create", after={"status": status}, actor=actor)
    if status == ClassBooking.Status.BOOKED:
        notify(
            member,
            "class_booked",
            {"class_name": locked_schedule.name, "starts_at": str(locked_schedule.starts_at)},
            actor=actor,
        )
    return booking


def cancel_booking(booking: ClassBooking, actor: Any = None) -> ClassBooking:
    """select_for_update() on the parent ClassSchedule (not the booking,
    not the waitlist queryset) so two concurrent cancellations on the same
    class serialize instead of both promoting a member into one freed slot.
    """
    promoted = None
    with transaction.atomic():
        schedule = ClassSchedule.objects.select_for_update().get(pk=booking.class_schedule_id)
        was_booked = booking.status == ClassBooking.Status.BOOKED
        before_status = booking.status
        booking.status = ClassBooking.Status.CANCELLED
        booking.save(update_fields=["status"])
        audit(
            booking,
            "update",
            before={"status": before_status},
            after={"status": "cancelled"},
            actor=actor,
        )

        if was_booked:
            promoted = (
                ClassBooking.objects.filter(
                    class_schedule=schedule, status=ClassBooking.Status.WAITLIST
                )
                .order_by("created_at")
                .first()
            )
            if promoted is not None:
                promoted.status = ClassBooking.Status.BOOKED
                promoted.save(update_fields=["status"])
                audit(
                    promoted,
                    "update",
                    before={"status": "waitlist"},
                    after={"status": "booked"},
                    actor=actor,
                )

    if promoted is not None:
        notify(promoted.member, "class_booking_promoted", {"class_name": schedule.name})
    return booking


# --- PT attendance + commission ----------------------------------------------


def record_pt_attendance(session: PTSession, attended: bool, actor: Any = None) -> PTSession:
    """Commission here is the trainer's pro-rated share of the pack price
    per delivered session (pack.price_npr / pack.sessions_total) — FR-7
    doesn't specify a percentage, and this "feeds Phase 9" per the FR's own
    note, so a future payroll phase can apply its own rate on top of these
    raw rows rather than this phase guessing at one.
    """
    was_attended = session.attended
    session.attended = attended
    session.save(update_fields=["attended"])

    if attended and not was_attended:
        with transaction.atomic():
            pack = PTPack.objects.select_for_update().get(pk=session.pack_id)
            pack.sessions_used += 1
            pack.save(update_fields=["sessions_used"])
            if pack.trainer_id and pack.sessions_total > 0:
                amount = (pack.price_npr / pack.sessions_total).quantize(Decimal("0.01"))
                TrainerCommission.objects.create(
                    org=pack.org,
                    gym=pack.gym,
                    trainer=pack.trainer,
                    source=TrainerCommission.Source.PT_SESSION,
                    amount_npr=amount,
                    period=session.scheduled_at.strftime("%Y-%m"),
                    pt_session=session,
                    pt_pack=pack,
                )
    return session
