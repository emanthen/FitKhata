from __future__ import annotations

from rest_framework import serializers

from core.crypto import decrypt_bytes, encrypt_bytes
from staff.models import (
    Advance,
    ChecklistCompletion,
    LeaveBalance,
    LeaveRequest,
    PayrollRun,
    Payslip,
    ShiftChecklist,
    ShiftTemplate,
    StaffAttendance,
    StaffProfile,
    StaffShift,
)

MAX_STAFF_BATCH_SIZE = 100


class StaffProfileSerializer(serializers.ModelSerializer):
    """bank_account/pan_no are owner-only on READ — redacted to None in
    to_representation() for anyone else, regardless of which permission
    class gates the view (see staff/views.py's docstring on why the
    ViewSet itself stays at IsManagerOrAbove). pan_no is a plain writable
    model field (redaction is output-only); bank_account has no model
    field of that name at all — bank_account_input is the write-only
    input, encrypted into bank_account_encrypted on save the same way
    GatewayCredentialSerializer packs its secret, and `bank_account` is a
    SerializerMethodField purely for decrypted output.
    """

    bank_account = serializers.SerializerMethodField()
    bank_account_input = serializers.CharField(write_only=True, required=False, allow_blank=True)
    full_name = serializers.CharField(source="user.full_name", read_only=True)

    class Meta:
        model = StaffProfile
        fields = [
            "id",
            "user",
            "full_name",
            "employment_type",
            "base_salary_npr",
            "hourly_rate_npr",
            "pan_no",
            "bank_name",
            "bank_account",
            "bank_account_input",
            "joined_on",
            "badge_code",
            "is_active",
        ]
        read_only_fields = ["id", "badge_code"]

    def _is_owner(self) -> bool:
        request = self.context.get("request")
        return bool(request) and getattr(request, "role", None) == "owner"

    def get_bank_account(self, obj: StaffProfile) -> str | None:
        if not self._is_owner() or not bytes(obj.bank_account_encrypted):
            return None
        return decrypt_bytes(bytes(obj.bank_account_encrypted)).decode("utf-8")

    def to_representation(self, instance: StaffProfile) -> dict:
        data = super().to_representation(instance)
        if not self._is_owner():
            data["pan_no"] = None
        return data

    def create(self, validated_data: dict) -> StaffProfile:
        raw_account = validated_data.pop("bank_account_input", "")
        validated_data["bank_account_encrypted"] = encrypt_bytes(
            raw_account.encode("utf-8")
        ) if raw_account else b""
        return super().create(validated_data)

    def update(self, instance: StaffProfile, validated_data: dict) -> StaffProfile:
        raw_account = validated_data.pop("bank_account_input", None)
        if raw_account is not None:
            validated_data["bank_account_encrypted"] = (
                encrypt_bytes(raw_account.encode("utf-8")) if raw_account else b""
            )
        return super().update(instance, validated_data)


class ShiftTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShiftTemplate
        fields = ["id", "weekday", "start", "end", "role"]


class StaffShiftSerializer(serializers.ModelSerializer):
    class Meta:
        model = StaffShift
        fields = ["id", "staff", "date", "start", "end", "template"]
        read_only_fields = ["id"]


class StaffAttendanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = StaffAttendance
        fields = ["id", "staff", "clock_in", "clock_out", "source"]
        read_only_fields = ["id"]


class StaffGateCheckinRowSerializer(serializers.Serializer):
    client_uuid = serializers.UUIDField()
    badge_code = serializers.CharField(max_length=30)
    scanned_at = serializers.DateTimeField()


class StaffGateCheckinsBatchSerializer(serializers.Serializer):
    checkins = StaffGateCheckinRowSerializer(many=True)

    def validate_checkins(self, value: list[dict]) -> list[dict]:
        if len(value) > MAX_STAFF_BATCH_SIZE:
            raise serializers.ValidationError(f"At most {MAX_STAFF_BATCH_SIZE} scans per batch.")
        if not value:
            raise serializers.ValidationError("At least one scan is required.")
        return value


class LeaveRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaveRequest
        fields = [
            "id",
            "staff",
            "from_date",
            "to_date",
            "kind",
            "reason",
            "status",
            "reviewed_by",
            "reviewed_at",
        ]
        read_only_fields = ["id", "status", "reviewed_by", "reviewed_at"]


class LeaveBalanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaveBalance
        fields = ["id", "staff", "kind", "days_available"]
        read_only_fields = ["id"]


class AdvanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Advance
        fields = ["id", "staff", "amount_npr", "date", "recovered_in_run"]
        read_only_fields = ["id"]


class PayslipSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payslip
        fields = [
            "id",
            "run",
            "staff",
            "base_npr",
            "commission_npr",
            "incentives_npr",
            "advances_npr",
            "tds_npr",
            "social_security_npr",
            "net_npr",
        ]
        read_only_fields = fields


class PayrollRunSerializer(serializers.ModelSerializer):
    payslips = PayslipSerializer(many=True, read_only=True)

    class Meta:
        model = PayrollRun
        fields = [
            "id",
            "period_bs",
            "status",
            "totals_npr",
            "finalized_by",
            "finalized_at",
            "payslips",
        ]
        read_only_fields = ["id", "status", "totals_npr", "finalized_by", "finalized_at"]


class ShiftChecklistSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShiftChecklist
        fields = ["id", "name", "items"]
        read_only_fields = ["id"]


class ChecklistCompletionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChecklistCompletion
        fields = ["id", "checklist", "date", "completed_by", "checked_items", "completed_at"]
        read_only_fields = ["id", "completed_by", "completed_at"]
