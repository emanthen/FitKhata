"""Public-facing serializers for FR-12.3's read endpoints -- deliberately
separate from members/serializers.py and billing/serializers.py's own
ModelSerializers (which are shaped for the admin console and can gain new
internal fields over time), not a reuse of them, so a third-party
Enterprise integration's contract never silently changes shape under it.
"""

from __future__ import annotations

from rest_framework import serializers

from billing.models import Invoice
from members.models import Member, Membership
from publicapi.models import ApiKey, WebhookDelivery, WebhookSubscription


class PublicMemberSerializer(serializers.ModelSerializer):
    class Meta:
        model = Member
        fields = ["id", "member_code", "full_name", "phone", "email", "status", "created_at"]
        read_only_fields = fields


class PublicMembershipSerializer(serializers.ModelSerializer):
    class Meta:
        model = Membership
        fields = ["id", "member", "plan", "start_date", "expiry_date", "status"]
        read_only_fields = fields


class PublicInvoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Invoice
        fields = ["id", "number", "status", "member", "total_npr", "bill_date"]
        read_only_fields = fields


class ApiKeyCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100)
    scopes = serializers.MultipleChoiceField(choices=ApiKey.Scope.choices)


class ApiKeySerializer(serializers.ModelSerializer):
    class Meta:
        model = ApiKey
        fields = ["id", "name", "key_prefix", "scopes", "created_at", "last_used_at", "revoked_at"]
        read_only_fields = fields


class WebhookSubscriptionCreateSerializer(serializers.Serializer):
    url = serializers.URLField(max_length=500)
    events = serializers.MultipleChoiceField(choices=WebhookSubscription.Event.choices)
    secret = serializers.CharField(max_length=200)


class WebhookSubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = WebhookSubscription
        fields = ["id", "url", "events", "is_active", "created_at"]
        read_only_fields = fields


class WebhookDeliverySerializer(serializers.ModelSerializer):
    class Meta:
        model = WebhookDelivery
        fields = [
            "id",
            "event",
            "status",
            "attempt_count",
            "response_status",
            "created_at",
            "last_attempted_at",
        ]
        read_only_fields = fields
