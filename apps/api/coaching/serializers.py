from __future__ import annotations

from rest_framework import serializers

from coaching.models import (
    BodyMeasurement,
    BodyMeasurementPhoto,
    ClassBooking,
    ClassSchedule,
    ClientProfile,
    CoachingReport,
    DietLog,
    DietPlan,
    Exercise,
    FoodItem,
    PTPack,
    PTSession,
    TrainerCommission,
    WorkoutLog,
    WorkoutPlan,
)


class ExerciseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Exercise
        fields = ["id", "name_en", "name_ne", "muscle_group", "equipment", "media_url", "is_active"]
        read_only_fields = fields


class FoodItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = FoodItem
        fields = [
            "id",
            "name_en",
            "name_ne",
            "kcal_per_100g",
            "protein_g_per_100g",
            "carbs_g_per_100g",
            "fat_g_per_100g",
        ]
        read_only_fields = fields


class ClientProfileSerializer(serializers.ModelSerializer):
    member_name = serializers.CharField(source="member.full_name", read_only=True)

    class Meta:
        model = ClientProfile
        fields = [
            "id",
            "member",
            "member_name",
            "trainer",
            "primary_goal",
            "starting_weight_kg",
            "target_weight_kg",
            "workout_plan",
            "diet_plan",
            "coach_notes",
            "consent_health_data",
            "consent_at",
            "created_at",
        ]
        read_only_fields = ["id", "consent_health_data", "consent_at", "created_at"]


class BodyMeasurementPhotoSerializer(serializers.ModelSerializer):
    """A fresh 5-minute signed URL per read — never stored, see
    coaching/storage.py::PrivateMediaStorage.
    """

    url = serializers.SerializerMethodField()

    class Meta:
        model = BodyMeasurementPhoto
        fields = ["id", "angle", "url"]
        read_only_fields = fields

    def get_url(self, obj: BodyMeasurementPhoto) -> str:
        return obj.image.url


class BodyMeasurementSerializer(serializers.ModelSerializer):
    photos = BodyMeasurementPhotoSerializer(many=True, read_only=True)

    class Meta:
        model = BodyMeasurement
        fields = [
            "id",
            "member",
            "measured_on",
            "weight_kg",
            "body_fat_pct",
            "measurements",
            "photos",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class WorkoutPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkoutPlan
        fields = ["id", "name", "split", "days", "created_by", "created_at"]
        read_only_fields = ["id", "created_by", "created_at"]


class WorkoutLogSerializer(serializers.ModelSerializer):
    exercise_name_en = serializers.CharField(source="exercise.name_en", read_only=True)

    class Meta:
        model = WorkoutLog
        fields = ["id", "member", "logged_on", "exercise", "exercise_name_en", "sets", "created_at"]
        read_only_fields = ["id", "created_at"]


class DietLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = DietLog
        fields = ["id", "member", "logged_on", "protein_g"]
        read_only_fields = ["id"]


class DietPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = DietPlan
        fields = ["id", "name", "kcal_target", "protein_g", "meals", "created_by", "created_at"]
        read_only_fields = ["id", "created_by", "created_at"]


class PTPackSerializer(serializers.ModelSerializer):
    class Meta:
        model = PTPack
        fields = [
            "id",
            "member",
            "trainer",
            "sessions_total",
            "sessions_used",
            "price_npr",
            "expires_on",
            "created_at",
        ]
        read_only_fields = ["id", "sessions_used", "created_at"]


class PTSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PTSession
        fields = ["id", "pack", "scheduled_at", "attended"]
        read_only_fields = ["id"]


class ClassScheduleSerializer(serializers.ModelSerializer):
    booked_count = serializers.SerializerMethodField()

    class Meta:
        model = ClassSchedule
        fields = ["id", "name", "trainer", "starts_at", "capacity", "booked_count", "created_at"]
        read_only_fields = ["id", "created_at"]

    def get_booked_count(self, obj: ClassSchedule) -> int:
        return obj.bookings.filter(status=ClassBooking.Status.BOOKED).count()


class ClassBookingSerializer(serializers.ModelSerializer):
    member_name = serializers.CharField(source="member.full_name", read_only=True)

    class Meta:
        model = ClassBooking
        fields = ["id", "class_schedule", "member", "member_name", "status", "created_at"]
        read_only_fields = fields


class TrainerCommissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = TrainerCommission
        fields = [
            "id",
            "trainer",
            "source",
            "amount_npr",
            "period",
            "pt_session",
            "pt_pack",
            "created_at",
        ]
        read_only_fields = fields


class CoachingReportSerializer(serializers.ModelSerializer):
    member_name = serializers.CharField(source="member.full_name", read_only=True, default="")

    class Meta:
        model = CoachingReport
        fields = [
            "id",
            "member",
            "member_name",
            "week_start",
            "kind",
            "flags",
            "suggestions",
            "status",
            "approved_by",
            "approved_at",
            "model",
            "tokens_used",
            "cost_npr",
            "created_at",
        ]
        read_only_fields = fields


class RejectReportSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, default="")
