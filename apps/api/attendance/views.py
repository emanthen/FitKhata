from __future__ import annotations

from datetime import UTC, datetime

from django.core import signing
from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsFrontDeskOrAbove, IsGateDevice, IsManagerOrAbove
from attendance.crypto import derive_device_key, encrypt_for_device
from attendance.pairing import generate_pairing_code, redeem_pairing_code
from attendance.serializers import (
    GateCheckinsBatchSerializer,
    GatePairingCodeSerializer,
    GatePairRequestSerializer,
    ManualCheckinSerializer,
)
from attendance.services import (
    RedCheckinRequiresReason,
    member_dues_npr,
    record_checkins_batch,
    record_manual_checkin,
    register_gate_device,
)
from core.context import system_context
from core.crypto import decrypt_bytes
from members.models import Member

MEMBER_PASS_SALT = "attendance.member-pass"
MEMBER_PASS_MAX_AGE = 2 * 365 * 24 * 60 * 60  # 2 years — see services docstring


class GatePairingCodeView(APIView):
    """Staff-side: generate a one-time code for a device to redeem."""

    permission_classes = [permissions.IsAuthenticated, IsManagerOrAbove]

    def post(self, request):
        if request.gym is None:
            return Response({"detail": "X-Gym-Id header is required."}, status=400)
        serializer = GatePairingCodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        code = generate_pairing_code(request.gym)
        return Response({"code": code, "expires_in": 600})


class GatePairView(APIView):
    """Device-side: redeem a pairing code, get back a permanent device
    token. No auth — the device has nothing yet; the code itself is the
    proof of authorization (a manager had to generate it).
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = GatePairRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        gym = redeem_pairing_code(data["code"])
        if gym is None:
            return Response({"detail": "Invalid or expired pairing code."}, status=400)

        device, raw_token = register_gate_device(gym, data["device_name"])
        return Response(
            {"device_id": device.pk, "gym_id": str(gym.pk), "token": raw_token},
            status=status.HTTP_201_CREATED,
        )


class GateSnapshotView(APIView):
    """Delta sync: members changed since `?since=` (ISO datetime; omit for a
    full sync), with qr_secret re-encrypted per-device (AES-GCM, key derived
    from this request's own raw device token — see attendance.crypto).
    """

    permission_classes = [IsGateDevice]

    def get(self, request):
        since_raw = request.query_params.get("since")
        since = None
        if since_raw:
            try:
                since = datetime.fromisoformat(since_raw)
            except ValueError:
                return Response({"detail": "`since` must be ISO 8601."}, status=400)

        members_qs = Member.objects.filter(gym=request.gate_device.gym)
        if since is not None:
            members_qs = members_qs.filter(updated_at__gt=since)

        device_key = derive_device_key(request.gate_device_raw_token)
        server_time = datetime.now(tz=UTC)

        payload = []
        for member in members_qs.select_related():
            membership = member.memberships.order_by("-expiry_date").first()
            raw_secret = decrypt_bytes(bytes(member.qr_secret))
            access_hours = membership.plan.access_hours if membership else {"always": True}
            payload.append(
                {
                    "member_code": member.member_code,
                    "member_id": member.pk,
                    "qr_secret": encrypt_for_device(device_key, raw_secret),
                    "status": member.status,
                    "expiry_date": membership.expiry_date.isoformat() if membership else None,
                    "access_hours": access_hours,
                    "dues_npr": str(member_dues_npr(member)),
                    "photo_url": member.photo.url if member.photo else None,
                    "card_uid": member.card_uid,
                    "updated_at": member.updated_at.isoformat(),
                }
            )

        return Response({"members": payload, "server_time": server_time.isoformat()})


class GateCheckinsBatchView(APIView):
    permission_classes = [IsGateDevice]

    def post(self, request):
        serializer = GateCheckinsBatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = record_checkins_batch(request.gate_device, serializer.validated_data["checkins"])
        return Response(result)


class ManualCheckinView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsFrontDeskOrAbove]

    def post(self, request):
        if request.gym is None:
            return Response({"detail": "X-Gym-Id header is required."}, status=400)
        serializer = ManualCheckinSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        member = get_object_or_404(Member, pk=data["member_id"], gym=request.gym)
        try:
            attendance = record_manual_checkin(member, request.user, reason=data["reason"])
        except RedCheckinRequiresReason as exc:
            return Response({"detail": str(exc)}, status=400)

        return Response({"id": attendance.pk, "check_in_at": attendance.check_in_at})


class MemberPassLinkView(APIView):
    """Staff action: issue a signed, long-lived link a member can open on
    their own phone to redeem their QR pass (see MemberPassView). Not a new
    member-login system — see the plan's decision on this.
    """

    permission_classes = [permissions.IsAuthenticated, IsFrontDeskOrAbove]

    def post(self, request):
        if request.gym is None:
            return Response({"detail": "X-Gym-Id header is required."}, status=400)
        member_id = request.data.get("member_id")
        member = get_object_or_404(Member, pk=member_id, gym=request.gym)
        token = signing.dumps({"member_id": member.pk}, salt=MEMBER_PASS_SALT)
        return Response({"token": token})


class MemberPassView(APIView):
    """Member-side: redeems the link above. No auth — the signed token
    itself is the proof; it's handed out by staff and only ever sent to the
    member it names.
    """

    permission_classes = [permissions.AllowAny]

    def get(self, request, token: str):
        try:
            data = signing.loads(token, salt=MEMBER_PASS_SALT, max_age=MEMBER_PASS_MAX_AGE)
        except signing.SignatureExpired:
            return Response({"detail": "This pass link has expired."}, status=400)
        except signing.BadSignature:
            return Response({"detail": "Invalid pass link."}, status=400)

        # No gym is scoped yet (unauthenticated, signed-token-only entry
        # point) — same bootstrapping case as register_gate_device.
        with system_context():
            member = get_object_or_404(Member, pk=data["member_id"])
            return Response(
                {
                    "member_id": member.pk,
                    "member_code": member.member_code,
                    "full_name": member.full_name,
                    "gym_code": member.gym.code,
                    "qr_secret_hex": decrypt_bytes(bytes(member.qr_secret)).hex(),
                }
            )
