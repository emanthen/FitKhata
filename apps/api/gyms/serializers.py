from __future__ import annotations

from rest_framework import serializers

from gyms.models import Gym, Organization


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = [
            "id",
            "name",
            "pan_vat_no",
            "is_vat_registered",
            "vat_inclusive_pricing",
            "saas_plan",
            "saas_status",
            "created_at",
        ]
        read_only_fields = ["id", "saas_plan", "saas_status", "created_at"]


class GymSerializer(serializers.ModelSerializer):
    class Meta:
        model = Gym
        fields = [
            "id",
            "org",
            "code",
            "name",
            "address",
            "city",
            "phone",
            "timezone",
            "settings",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]
