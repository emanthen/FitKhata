from __future__ import annotations

from rest_framework import serializers

from notifications.models import Announcement, Broadcast, Notification, PushSubscription, Template


class TemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Template
        fields = [
            "id",
            "org",
            "key",
            "channel",
            "language",
            "body",
            "whatsapp_template_name",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "org", "created_at", "updated_at"]


class NotificationSerializer(serializers.ModelSerializer):
    member_name = serializers.CharField(source="member.full_name", read_only=True)

    class Meta:
        model = Notification
        fields = [
            "id",
            "member",
            "member_name",
            "channel",
            "template_key",
            "language",
            "status",
            "attempt_count",
            "provider_ref",
            "cost_npr",
            "error",
            "sent_at",
            "delivered_at",
            "fallback_of",
            "created_at",
        ]
        read_only_fields = fields


class PushSubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PushSubscription
        fields = ["id", "member", "endpoint", "keys", "user_agent", "last_seen_at"]
        read_only_fields = ["id", "last_seen_at"]


class BroadcastSerializer(serializers.ModelSerializer):
    class Meta:
        model = Broadcast
        fields = [
            "id",
            "segment",
            "segment_value",
            "channel",
            "body_ne",
            "body_en",
            "recipient_count",
            "cost_npr",
            "created_by",
            "sent_at",
            "created_at",
        ]
        read_only_fields = fields


class BroadcastEstimateSerializer(serializers.Serializer):
    segment = serializers.ChoiceField(choices=Broadcast.Segment.choices)
    segment_value = serializers.CharField(required=False, allow_blank=True, default="")
    channel = serializers.ChoiceField(choices=Template.Channel.choices)


class SendBroadcastSerializer(BroadcastEstimateSerializer):
    body_ne = serializers.CharField()
    body_en = serializers.CharField()


class AnnouncementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Announcement
        fields = [
            "id",
            "title",
            "body_ne",
            "body_en",
            "is_active",
            "starts_at",
            "ends_at",
            "created_by",
            "created_at",
        ]
        read_only_fields = ["id", "created_by", "created_at"]
