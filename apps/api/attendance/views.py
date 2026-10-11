from __future__ import annotations

from datetime import UTC, date, datetime

from django.core import signing
from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.otp import OtpLocked, OtpRateLimited, send_otp, verify_otp
from accounts.permissions import IsFrontDeskOrAbove, IsGateDevice, IsManagerOrAbove
from accounts.sms import get_sms_provider
from attendance.crypto import derive_device_key, encrypt_for_device
from attendance.domain.streak import compute_streaks
from attendance.models import Attendance
from attendance.pairing import generate_pairing_code, redeem_pairing_code
from attendance.serializers import (
    GateCheckinsBatchSerializer,
    GatePairingCodeSerializer,
    GatePairRequestSerializer,
    ManualCheckinSerializer,
    MemberLoginOtpSendSerializer,
    MemberLoginOtpVerifySerializer,
)
from attendance.services import (
    RedCheckinRequiresReason,
    member_dues_npr,
    record_checkins_batch,
    record_manual_checkin,
    register_gate_device,
    touch_device_heartbeat,
)
from core.context import system_context
from core.crypto import decrypt_bytes
from members.models import Member
from staff.models import StaffProfile

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

        # Phase 9 staff badges — additive key only, member sync above is
        # completely untouched. STAFF- prefixed badge_code (vs. member_
        # code's "{gym.code}-####") keeps the two lists unambiguous even
        # if a kiosk build merges them before matching a scanned token.
        staff_qs = StaffProfile.objects.filter(gym=request.gate_device.gym, is_active=True)
        if since is not None:
            staff_qs = staff_qs.filter(updated_at__gt=since)
        staff_payload = [
            {
                "badge_code": staff.badge_code,
                "staff_id": staff.pk,
                "qr_secret": encrypt_for_device(device_key, decrypt_bytes(bytes(staff.qr_secret))),
                "updated_at": staff.updated_at.isoformat(),
            }
            for staff in staff_qs
        ]

        return Response(
            {
                "members": payload,
                "staff": staff_payload,
                "server_time": server_time.isoformat(),
            }
        )


class GateCheckinsBatchView(APIView):
    permission_classes = [IsGateDevice]

    def post(self, request):
        serializer = GateCheckinsBatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = record_checkins_batch(request.gate_device, serializer.validated_data["checkins"])
        return Response(result)


class GateHeartbeatView(APIView):
    """Bridge/kiosk liveness ping -- see attendance.tasks.alert_offline_gate_devices
    for the other side of this (owner SMS when a device goes quiet)."""

    permission_classes = [IsGateDevice]

    def post(self, request):
        touch_device_heartbeat(request.gate_device)
        return Response(status=status.HTTP_204_NO_CONTENT)


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


class MemberLoginOtpSendView(APIView):
    """Member self-login, step 1. Shares accounts.otp's phone-keyed
    primitives with staff login (OtpSendView) -- see the plan's accepted
    judgment call on the resulting same-phone collision risk.
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = MemberLoginOtpSendSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone = serializer.validated_data["phone"]

        try:
            code = send_otp(phone)
        except OtpRateLimited as exc:
            return Response(
                {"detail": "Too many OTP requests.", "retry_after": exc.retry_after},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        get_sms_provider().send(phone, f"Your FitKhata code is {code}. Valid for 5 minutes.")
        return Response(status=status.HTTP_204_NO_CONTENT)


class MemberLoginOtpVerifyView(APIView):
    """Member self-login, step 2. Requires gym_code (pre-filled from a
    `?gym=` link on each gym's own poster/QR) rather than listing every gym
    a phone matches -- a phone can legitimately belong to members at
    unrelated gyms, and listing them would leak membership existence at one
    gym to anyone who only proved they own that phone. On success, mints
    and returns the exact same shape MemberPassView does, plus the token
    itself, so the client's existing setCachedPass needs no changes.
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = MemberLoginOtpVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            correct = verify_otp(data["phone"], data["code"])
        except OtpLocked as exc:
            return Response(
                {"detail": "Too many wrong attempts.", "retry_after": exc.retry_after},
                status=status.HTTP_423_LOCKED,
            )
        if not correct:
            return Response({"detail": "Incorrect code."}, status=status.HTTP_400_BAD_REQUEST)

        with system_context():
            member = Member.objects.filter(
                phone=data["phone"], gym__code=data["gym_code"]
            ).first()
            if member is None:
                return Response(
                    {"detail": "No member found with this phone at this gym."}, status=404
                )
            token = signing.dumps({"member_id": member.pk}, salt=MEMBER_PASS_SALT)
            return Response(
                {
                    "token": token,
                    "member_id": member.pk,
                    "member_code": member.member_code,
                    "full_name": member.full_name,
                    "gym_code": member.gym.code,
                    "qr_secret_hex": decrypt_bytes(bytes(member.qr_secret)).hex(),
                }
            )


class MemberAttendanceCalendarView(APIView):
    """FR-8.3/8.4: distinct visit dates (for the BS/AD calendar) plus the
    current/longest streak, computed by the pure attendance.domain.streak
    function. 7/30/100-day badges are a client-side comparison against
    current_streak -- nothing is stored for them.
    """

    permission_classes = [permissions.AllowAny]

    def get(self, request, token: str):
        try:
            data = signing.loads(token, salt=MEMBER_PASS_SALT, max_age=MEMBER_PASS_MAX_AGE)
        except signing.SignatureExpired:
            return Response({"detail": "This pass link has expired."}, status=400)
        except signing.BadSignature:
            return Response({"detail": "Invalid pass link."}, status=400)

        with system_context():
            member = get_object_or_404(Member, pk=data["member_id"])
            visit_dates: list[date] = list(
                Attendance.objects.filter(member=member)
                .values_list("check_in_at__date", flat=True)
                .distinct()
            )
            current_streak, longest_streak = compute_streaks(visit_dates)
            return Response(
                {
                    "visit_dates": [d.isoformat() for d in sorted(visit_dates)],
                    "current_streak": current_streak,
                    "longest_streak": longest_streak,
                }
            )
