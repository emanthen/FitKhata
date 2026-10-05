from __future__ import annotations

from rest_framework import serializers

from accounts.models import DeviceSession, StaffRole, User, phone_validator


class OtpSendSerializer(serializers.Serializer):
    phone = serializers.CharField(validators=[phone_validator])


class OtpVerifySerializer(serializers.Serializer):
    phone = serializers.CharField(validators=[phone_validator])
    code = serializers.CharField(min_length=6, max_length=6)


class RegisterSerializer(serializers.Serializer):
    registration_token = serializers.CharField()
    full_name = serializers.CharField(max_length=200)
    password = serializers.CharField(write_only=True, min_length=8)


class LoginSerializer(serializers.Serializer):
    identifier = serializers.CharField()  # phone or email
    password = serializers.CharField(write_only=True)
    totp_code = serializers.CharField(required=False, allow_blank=True)


class TotpConfirmSerializer(serializers.Serializer):
    code = serializers.CharField(min_length=6, max_length=6)


class DeviceSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviceSession
        fields = ["id", "user_agent", "ip", "created_at", "last_used_at", "revoked_at"]
        read_only_fields = fields


class StaffInviteCreateSerializer(serializers.Serializer):
    gym_id = serializers.UUIDField(required=False, allow_null=True)
    role = serializers.ChoiceField(choices=StaffRole.Role.choices)


class StaffInviteAcceptSerializer(serializers.Serializer):
    token = serializers.CharField()
    phone = serializers.CharField(validators=[phone_validator])
    full_name = serializers.CharField(max_length=200)
    password = serializers.CharField(write_only=True, min_length=8)


class StaffRoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = StaffRole
        fields = ["id", "org", "gym", "user", "role", "is_active", "created_at"]
        read_only_fields = ["id", "org", "created_at"]


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "phone", "email", "full_name", "locale"]
        read_only_fields = ["id"]
