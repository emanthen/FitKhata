from __future__ import annotations

from rest_framework import serializers

from core.validators import strip_exif, validate_image_file, validate_pdf_file
from members.models import (
    AddOn,
    ImportJob,
    Member,
    MemberFeedback,
    Membership,
    Plan,
    PromoCode,
    Waiver,
)


class MemberSerializer(serializers.ModelSerializer):
    class Meta:
        model = Member
        fields = [
            "id",
            "member_code",
            "full_name",
            "phone",
            "email",
            "gender",
            "dob",
            "emergency_contact",
            "photo",
            "tags",
            "status",
            "risk_state",
            "churn_score",
            "last_check_in_at",
            "marketing_opt_in",
            "notifications_opt_out",
            "language",
            "referred_by",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "member_code",
            "status",
            "risk_state",
            "churn_score",
            "last_check_in_at",
            "created_at",
        ]

    def validate_photo(self, value):
        if value is None:
            return value
        validate_image_file(value)
        return strip_exif(value)


class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = [
            "id",
            "name",
            "duration_days",
            "price_npr",
            "joining_fee_npr",
            "access_hours",
            "pt_sessions",
            "max_freeze_days",
            "is_active",
        ]
        read_only_fields = ["id"]


class AddOnSerializer(serializers.ModelSerializer):
    class Meta:
        model = AddOn
        fields = ["id", "name", "price_npr", "kind"]
        read_only_fields = ["id"]


class PromoCodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = PromoCode
        fields = [
            "id",
            "code",
            "kind",
            "value",
            "valid_from",
            "valid_to",
            "usage_limit",
            "per_member_once",
            "times_used",
        ]
        read_only_fields = ["id", "times_used"]


class MembershipSerializer(serializers.ModelSerializer):
    class Meta:
        model = Membership
        fields = [
            "id",
            "member",
            "plan",
            "start_date",
            "expiry_date",
            "status",
            "invoice",
            "created_at",
        ]
        read_only_fields = fields


class SellMembershipSerializer(serializers.Serializer):
    plan_id = serializers.PrimaryKeyRelatedField(queryset=Plan.objects.all())
    promo_code = serializers.CharField(required=False, allow_blank=True)
    addon_ids = serializers.PrimaryKeyRelatedField(
        queryset=AddOn.objects.all(), many=True, required=False
    )


class TransferMemberSerializer(serializers.Serializer):
    gym_id = serializers.UUIDField()


class WaiverSerializer(serializers.ModelSerializer):
    class Meta:
        model = Waiver
        fields = ["id", "member", "signed_pdf", "signed_at", "ip"]
        read_only_fields = ["id", "signed_at", "ip"]

    def validate_signed_pdf(self, value):
        validate_pdf_file(value)
        return value


class MemberFeedbackSerializer(serializers.ModelSerializer):
    class Meta:
        model = MemberFeedback
        fields = ["id", "member", "message", "created_at"]
        read_only_fields = fields


class MemberFeedbackCreateSerializer(serializers.Serializer):
    message = serializers.CharField(max_length=1000)


class ImportJobSerializer(serializers.ModelSerializer):
    class Meta:
        model = ImportJob
        fields = [
            "id",
            "status",
            "total_rows",
            "success_count",
            "error_report",
            "created_at",
        ]
        read_only_fields = fields
