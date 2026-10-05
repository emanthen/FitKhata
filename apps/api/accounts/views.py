from __future__ import annotations

import base64

from django.core import signing
from django.db.models import Q
from django_otp.plugins.otp_totp.models import TOTPDevice
from rest_framework import permissions, status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import DeviceSession, StaffRole, User
from accounts.otp import OtpLocked, OtpRateLimited, send_otp, verify_otp
from accounts.permissions import IsManagerOrAbove
from accounts.serializers import (
    DeviceSessionSerializer,
    LoginSerializer,
    OtpSendSerializer,
    OtpVerifySerializer,
    RegisterSerializer,
    StaffInviteAcceptSerializer,
    StaffInviteCreateSerializer,
    StaffRoleSerializer,
    TotpConfirmSerializer,
)
from accounts.sms import get_sms_provider
from accounts.tokens import (
    issue_tokens_for_user,
    make_invite_token,
    make_registration_token,
    read_invite_token,
    read_registration_token,
    revoke_device_session,
)
from core.context import system_context


class OtpSendView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = OtpSendSerializer(data=request.data)
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


class OtpVerifyView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = OtpVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone = serializer.validated_data["phone"]
        code = serializer.validated_data["code"]

        try:
            correct = verify_otp(phone, code)
        except OtpLocked as exc:
            return Response(
                {"detail": "Too many wrong attempts.", "retry_after": exc.retry_after},
                status=status.HTTP_423_LOCKED,
            )
        if not correct:
            return Response({"detail": "Incorrect code."}, status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.filter(phone=phone).first()
        if user is None:
            # verify_otp() already deleted the code on this successful check
            # (one-time use) — /register can't re-verify the same code, so
            # hand the client proof of this check instead.
            return Response(
                {
                    "verified": True,
                    "user_exists": False,
                    "registration_token": make_registration_token(phone),
                }
            )

        return Response(
            {"verified": True, "user_exists": True, **issue_tokens_for_user(user, request)}
        )


class RegisterView(APIView):
    """Creates a brand-new account using the registration_token from a
    successful OtpVerifyView call — the only way to get a first account at
    all (the onboarding wizard's org-creation step requires auth, so someone
    has to exist before it).
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            phone = read_registration_token(data["registration_token"])
        except signing.SignatureExpired:
            return Response({"detail": "Verify your phone again — that took too long."}, status=400)
        except signing.BadSignature:
            return Response({"detail": "Invalid registration token."}, status=400)

        if User.objects.filter(phone=phone).exists():
            return Response({"detail": "An account with this phone already exists."}, status=400)

        user = User.objects.create_user(
            phone=phone, password=data["password"], full_name=data["full_name"]
        )
        return Response(issue_tokens_for_user(user, request), status=status.HTTP_201_CREATED)


class TokenReissueView(APIView):
    """Mints a fresh token pair with up-to-date org_id/gym_ids/role claims
    and re-evaluates requires_totp_setup.

    Needed because those are only computed at token-issuance time
    (login/register/invite-accept) — a user who registers and then creates
    an org in the *same* session becomes an owner without ever triggering
    the mandatory-TOTP check, since that only fires at issuance. The web
    onboarding wizard calls this right after org creation for exactly that
    reason.
    """

    def post(self, request):
        return Response(issue_tokens_for_user(request.user, request))


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        user = User.objects.filter(
            Q(phone=data["identifier"]) | Q(email=data["identifier"])
        ).first()
        if user is None or not user.is_active or not user.check_password(data["password"]):
            return Response({"detail": "Invalid credentials."}, status=status.HTTP_401_UNAUTHORIZED)

        device = user.totpdevice_set.filter(confirmed=True).first()  # type: ignore[attr-defined]
        if device is not None:
            totp_code = data.get("totp_code", "")
            if not totp_code or not device.verify_token(totp_code):
                return Response({"detail": "totp_required"}, status=status.HTTP_401_UNAUTHORIZED)

        return Response(issue_tokens_for_user(user, request))


class TotpSetupView(APIView):
    def post(self, request):
        # Reuses any existing unconfirmed device instead of always deleting
        # + recreating — a repeat call (React dev-mode double effect, a
        # retried request, revisiting the page) must keep returning the same
        # secret, since TotpConfirmView checks the latest unconfirmed device
        # and a stale displayed secret from a since-replaced device would
        # never verify.
        device = (
            TOTPDevice.objects.filter(user=request.user, confirmed=False)
            .order_by("-id")
            .first()
        )
        if device is None:
            device = TOTPDevice.objects.create(user=request.user, name="default", confirmed=False)
        # base32, not device.key's hex — authenticator apps expect base32 for
        # manual entry, and it's what's already embedded in otpauth_url.
        secret = base64.b32encode(device.bin_key).decode()
        return Response({"secret": secret, "otpauth_url": device.config_url})


class TotpConfirmView(APIView):
    def post(self, request):
        serializer = TotpConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        device = (
            TOTPDevice.objects.filter(user=request.user, confirmed=False)
            .order_by("-id")
            .first()
        )
        if device is None or not device.verify_token(serializer.validated_data["code"]):
            return Response({"detail": "Incorrect code."}, status=status.HTTP_400_BAD_REQUEST)
        device.confirmed = True
        device.save(update_fields=["confirmed"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class DeviceSessionListView(APIView):
    def get(self, request):
        sessions = DeviceSession.objects.filter(user=request.user, revoked_at__isnull=True)
        return Response(DeviceSessionSerializer(sessions, many=True).data)


class DeviceSessionRevokeView(APIView):
    def post(self, request, session_id):
        session = DeviceSession.objects.filter(user=request.user, pk=session_id).first()
        if session is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        revoke_device_session(session)
        return Response(status=status.HTTP_204_NO_CONTENT)


class StaffInviteCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsManagerOrAbove]

    def post(self, request):
        serializer = StaffInviteCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if request.gym is None:
            return Response({"detail": "X-Gym-Id header is required."}, status=400)

        gym_id = serializer.validated_data.get("gym_id")
        token = make_invite_token(
            org_id=str(request.gym.org_id),
            gym_id=str(gym_id) if gym_id else str(request.gym.pk),
            role=serializer.validated_data["role"],
            invited_by=str(request.user.pk),
        )
        return Response({"token": token})


class StaffInviteAcceptView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = StaffInviteAcceptSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            invite = read_invite_token(data["token"])
        except signing.SignatureExpired:
            return Response({"detail": "This invite link has expired."}, status=400)
        except signing.BadSignature:
            return Response({"detail": "Invalid invite link."}, status=400)

        # Creating the StaffRole here is the same bootstrapping case as
        # OrganizationCreateView/GymCreateView: no gym is selected yet in
        # this anonymous request, so RLS would block the insert otherwise.
        with system_context():
            user, created = User.objects.get_or_create(
                phone=data["phone"],
                defaults={"full_name": data["full_name"]},
            )
            if created:
                user.set_password(data["password"])
                user.save(update_fields=["password"])

            StaffRole.objects.update_or_create(
                user=user,
                org_id=invite["org_id"],
                gym_id=invite["gym_id"],
                role=invite["role"],
                defaults={"is_active": True},
            )

        return Response(issue_tokens_for_user(user, request))


class StaffRoleViewSet(viewsets.ModelViewSet):
    """Not TenantViewSet-based: StaffRole's nullable gym (org-wide roles)
    doesn't fit the standard single-gym TenantQuerySet.for_gym shape, so this
    mirrors the RLS policy's OR-logic explicitly instead. RLS itself (not
    this queryset) is still the actual security boundary.
    """

    serializer_class = StaffRoleSerializer
    permission_classes = [permissions.IsAuthenticated, IsManagerOrAbove]
    queryset = StaffRole.objects.all()

    def get_queryset(self):
        if self.request.gym is None:
            return StaffRole.objects.none()
        return StaffRole.objects.filter(
            Q(gym=self.request.gym) | Q(gym__isnull=True, org=self.request.gym.org)
        )

    def perform_create(self, serializer):
        serializer.save(org=self.request.gym.org, gym=self.request.gym)


class MyGymsView(APIView):
    """Lists every gym the caller has an active StaffRole for — branch-
    specific or org-wide. Needed before a gym is even selected, so it runs
    under system_context() rather than the normal per-gym RLS scope.
    """

    def get(self, request):
        from gyms.models import Gym

        with system_context():
            gym_ids = set(
                StaffRole.objects.filter(
                    user=request.user, is_active=True, gym__isnull=False
                ).values_list("gym_id", flat=True)
            )
            org_ids = set(
                StaffRole.objects.filter(
                    user=request.user, is_active=True, gym__isnull=True
                ).values_list("org_id", flat=True)
            )
            gyms = Gym.objects.filter(Q(pk__in=gym_ids) | Q(org_id__in=org_ids)).values(
                "id", "org_id", "code", "name", "city"
            )
            return Response(list(gyms))
