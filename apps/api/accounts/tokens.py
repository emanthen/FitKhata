"""JWT issuance with custom claims, device-session bookkeeping, and the
staff-invite signed-token helpers (FR-1.4 — stateless, no StaffInvite model).
"""

from __future__ import annotations

from django.core import signing
from django.http import HttpRequest
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import DeviceSession, StaffRole, User
from core.context import system_context

ROLE_RANK = {"owner": 3, "manager": 2, "front_desk": 1, "trainer": 0}
INVITE_SALT = "accounts.staff-invite"
INVITE_MAX_AGE = 72 * 60 * 60  # 72h
REGISTRATION_SALT = "accounts.registration"
REGISTRATION_MAX_AGE = 10 * 60  # 10 minutes


def _client_ip(request: HttpRequest | None) -> str | None:
    if request is None:
        return None
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    return forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR")


def issue_tokens_for_user(user: User, request: HttpRequest | None = None) -> dict:
    """Issues an access/refresh pair with org_id/gym_ids/role claims, and
    records a DeviceSession for the "device sessions" list/revoke UI.

    Claims are a point-in-time convenience for the client's own UI — never
    the source of truth for authorization, which TenantMiddleware re-derives
    from StaffRole fresh on every request.
    """
    # Called from anonymous entry points (login, OTP verify, invite accept) —
    # no gym is selected yet, so app.gym_ids is empty and RLS would block
    # this otherwise. Same bootstrapping case as MyGymsView.
    with system_context():
        roles = list(
            StaffRole.objects.filter(user=user, is_active=True).values_list(
                "org_id", "gym_id", "role"
            )
        )
    org_id = str(roles[0][0]) if roles else None
    gym_ids = sorted({str(gym_id) for _, gym_id, _ in roles if gym_id is not None})
    role = max((r for _, _, r in roles), key=lambda r: ROLE_RANK.get(r, -1), default=None)

    refresh = RefreshToken.for_user(user)
    refresh["org_id"] = org_id
    refresh["gym_ids"] = gym_ids
    refresh["role"] = role
    refresh["is_platform_staff"] = user.is_staff

    DeviceSession.objects.create(
        user=user,
        jti=refresh["jti"],
        user_agent=(request.META.get("HTTP_USER_AGENT", "") if request else ""),
        ip=_client_ip(request),
    )

    # django-otp's reverse accessor isn't in django-stubs' User model shape.
    has_totp = user.totpdevice_set.filter(confirmed=True).exists()  # type: ignore[attr-defined]
    # Platform staff (saas.permissions.IsPlatformStaff) need 2FA just as
    # much as a gym owner does — same enforcement path, no new plumbing.
    requires_totp_setup = (role == "owner" or user.is_staff) and not has_totp

    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
        "requires_totp_setup": requires_totp_setup,
    }


def revoke_device_session(session: DeviceSession) -> None:
    from django.utils import timezone

    outstanding = OutstandingToken.objects.filter(jti=session.jti).first()
    if outstanding is not None:
        BlacklistedToken.objects.get_or_create(token=outstanding)
    session.revoked_at = timezone.now()
    session.save(update_fields=["revoked_at"])


def make_invite_token(*, org_id: str, gym_id: str | None, role: str, invited_by: str) -> str:
    return signing.dumps(
        {"org_id": org_id, "gym_id": gym_id, "role": role, "invited_by": invited_by},
        salt=INVITE_SALT,
    )


def read_invite_token(token: str) -> dict:
    """Raises django.core.signing.BadSignature / SignatureExpired on an
    invalid or expired (>72h) token."""
    return signing.loads(token, salt=INVITE_SALT, max_age=INVITE_MAX_AGE)


def make_registration_token(phone: str) -> str:
    """Proves phone ownership for the registration step that follows a
    successful OTP verify. Needed because verify_otp() deletes the code on
    success (one-time use) — a plain resubmission of the same {phone, code}
    to /register would always fail the second check.
    """
    return signing.dumps({"phone": phone}, salt=REGISTRATION_SALT)


def read_registration_token(token: str) -> str:
    """Returns the phone number. Raises BadSignature/SignatureExpired on an
    invalid or expired (>10 min) token."""
    return signing.loads(token, salt=REGISTRATION_SALT, max_age=REGISTRATION_MAX_AGE)["phone"]
