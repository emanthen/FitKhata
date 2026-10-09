from __future__ import annotations

from decimal import Decimal

from rest_framework import serializers

from retention.models import Campaign, FreezeRequest, MembershipFreeze, RetentionCall


class RetentionCallSerializer(serializers.ModelSerializer):
    member_name = serializers.CharField(source="member.full_name", read_only=True)
    member_phone = serializers.CharField(source="member.phone", read_only=True)

    class Meta:
        model = RetentionCall
        fields = [
            "id",
            "member",
            "member_name",
            "member_phone",
            "queue_date",
            "assigned_to",
            "outcome",
            "call_back_on",
            "notes",
            "completed_at",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "member",
            "member_name",
            "member_phone",
            "queue_date",
            "assigned_to",
            "outcome",
            "call_back_on",
            "notes",
            "completed_at",
            "created_at",
        ]


class CompleteCallSerializer(serializers.Serializer):
    outcome = serializers.ChoiceField(choices=RetentionCall.Outcome.choices)
    call_back_on = serializers.DateField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        if attrs["outcome"] == RetentionCall.Outcome.CALL_BACK and not attrs.get("call_back_on"):
            raise serializers.ValidationError(
                {"call_back_on": "Required when outcome is call_back."}
            )
        return attrs


class MembershipFreezeSerializer(serializers.ModelSerializer):
    member_name = serializers.CharField(source="membership.member.full_name", read_only=True)

    class Meta:
        model = MembershipFreeze
        fields = [
            "id",
            "membership",
            "member_name",
            "batch_id",
            "reason",
            "start_date",
            "end_date",
            "days",
            "previous_expiry",
            "fee_npr",
            "reverted_at",
            "created_at",
        ]
        read_only_fields = fields


class FreezeRangeSerializer(serializers.Serializer):
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    reason = serializers.ChoiceField(choices=MembershipFreeze.Reason.choices)

    def validate(self, attrs):
        if attrs["end_date"] < attrs["start_date"]:
            raise serializers.ValidationError({"end_date": "Must be on or after start_date."})
        return attrs


class IndividualFreezeSerializer(FreezeRangeSerializer):
    membership_id = serializers.IntegerField()
    fee_npr = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, default=Decimal("0")
    )


class FreezeRequestSerializer(serializers.ModelSerializer):
    member_name = serializers.CharField(source="member.full_name", read_only=True)

    class Meta:
        model = FreezeRequest
        fields = [
            "id",
            "member",
            "member_name",
            "membership",
            "start_date",
            "end_date",
            "reason",
            "status",
            "reviewed_by",
            "reviewed_at",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "member",
            "member_name",
            "status",
            "reviewed_by",
            "reviewed_at",
            "created_at",
        ]


class MemberFreezeRequestCreateSerializer(serializers.Serializer):
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    reason = serializers.CharField(max_length=500)

    def validate(self, attrs):
        if attrs["end_date"] < attrs["start_date"]:
            raise serializers.ValidationError({"end_date": "Must be on or after start_date."})
        return attrs


class CampaignSerializer(serializers.ModelSerializer):
    class Meta:
        model = Campaign
        fields = [
            "id",
            "kind",
            "promo",
            "sent_count",
            "converted_count",
            "created_at",
        ]
        read_only_fields = ["id", "sent_count", "converted_count", "created_at"]


class SendCampaignSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=Campaign.Kind.choices)
    promo_code = serializers.CharField(required=False, allow_blank=True)

    def validate_promo_code(self, value):
        return value.strip()
