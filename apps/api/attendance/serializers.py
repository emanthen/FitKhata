from __future__ import annotations

from rest_framework import serializers

from attendance.models import Attendance


class GatePairingCodeSerializer(serializers.Serializer):
    device_name = serializers.CharField(max_length=100)


class GatePairRequestSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=6, min_length=6)
    device_name = serializers.CharField(max_length=100)


MAX_BATCH_SIZE = 100


class GateCheckinRowSerializer(serializers.Serializer):
    client_uuid = serializers.UUIDField()
    member_code = serializers.CharField(max_length=20)
    check_in_at = serializers.DateTimeField()
    # Field literally named "source" is fine at runtime (DRF fields commonly
    # are) — drf-stubs just types Field.source at the class level, so mypy
    # sees this as an incompatible override of an attribute that isn't
    # really the same thing.
    source = serializers.ChoiceField(choices=Attendance.Source.choices)  # type: ignore[assignment]


class GateCheckinsBatchSerializer(serializers.Serializer):
    checkins = GateCheckinRowSerializer(many=True)

    def validate_checkins(self, value: list[dict]) -> list[dict]:
        if len(value) > MAX_BATCH_SIZE:
            raise serializers.ValidationError(f"At most {MAX_BATCH_SIZE} check-ins per batch.")
        if not value:
            raise serializers.ValidationError("At least one check-in is required.")
        return value


class ManualCheckinSerializer(serializers.Serializer):
    member_id = serializers.IntegerField()
    reason = serializers.CharField(required=False, allow_blank=True, default="")


class AttendanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Attendance
        fields = [
            "id",
            "member",
            "check_in_at",
            "source",
            "correction_reason",
            "created_at",
        ]
        read_only_fields = fields
