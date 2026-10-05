from __future__ import annotations

import uuid
from collections.abc import Callable

from django.db import connection, transaction
from django.db.models import Q
from django.http import HttpRequest, HttpResponse
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

GYM_HEADER = "HTTP_X_GYM_ID"
ROLE_RANK = {"owner": 3, "manager": 2, "front_desk": 1, "trainer": 0}


class TenantMiddleware:
    """Resolves the caller and the active gym, and scopes Postgres RLS to it.

    Django's AuthenticationMiddleware only populates request.user for session
    auth — SimpleJWT normally only runs inside DRF's dispatch(), too late for
    middleware. This calls JWTAuthentication directly (it only needs
    request.headers, so it works on a plain HttpRequest) so tenant scoping
    can live here, literally in middleware, per CLAUDE.md rule 2b, and apply
    uniformly to DRF and plain Django views alike. DRF's own configured
    JWTAuthentication still runs too on DRF views — a harmless redundant
    decode, not a correctness issue.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response
        self.jwt_auth = JWTAuthentication()

    def __call__(self, request: HttpRequest) -> HttpResponse:
        request.gym = None  # type: ignore[attr-defined]
        request.role = None  # type: ignore[attr-defined]
        request.gate_device = None  # type: ignore[attr-defined]

        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        if auth_header.startswith("Device "):
            return self._handle_device_auth(request, auth_header)

        user = self._authenticate(request)
        if user is None:
            return self.get_response(request)
        request.user = user  # type: ignore[assignment]

        gym, role = self._resolve_gym(request, user)
        request.gym = gym  # type: ignore[attr-defined]
        request.role = role  # type: ignore[attr-defined]

        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('app.user_id', %s, true)", [str(user.pk)])
                cursor.execute(
                    "SELECT set_config('app.gym_ids', %s, true)", [str(gym.pk) if gym else ""]
                )
            return self.get_response(request)

    def _handle_device_auth(self, request: HttpRequest, auth_header: str) -> HttpResponse:
        """A paired device is permanently bound to one gym — skip the
        StaffRole/X-Gym-Id resolution entirely, there's no role to rank and
        no header to trust-or-not. IsGateDevice (accounts.permissions) is
        what actually gates access; an unrecognized/revoked token here just
        leaves request.gate_device None, same "degrade, don't hard-fail" as
        _resolve_gym's stale-header handling.
        """
        from attendance.authentication import authenticate_device

        device, raw_token = authenticate_device(auth_header)
        if device is None:
            return self.get_response(request)

        request.gate_device = device  # type: ignore[attr-defined]
        request.gate_device_raw_token = raw_token  # type: ignore[attr-defined]
        request.gym = device.gym  # type: ignore[attr-defined]

        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('app.user_id', '', true)")
                cursor.execute(
                    "SELECT set_config('app.gym_ids', %s, true)", [str(device.gym_id)]
                )
            return self.get_response(request)

    def _authenticate(self, request: HttpRequest):
        try:
            # JWTAuthentication only touches request.headers/.META, which a
            # plain HttpRequest has too — this works at runtime despite the
            # DRF Request type hint.
            result = self.jwt_auth.authenticate(request)  # type: ignore[arg-type]
        except (InvalidToken, TokenError):
            return None
        return result[0] if result else None

    def _resolve_gym(self, request: HttpRequest, user):
        """Returns (gym, role) — both None if X-Gym-Id is absent, malformed,
        or names a gym this user has no active role on.

        Deliberately degrades to "no gym selected" rather than hard-failing
        the request: a stale/wrong X-Gym-Id is routine client state (e.g. a
        browser that still has a previous identity's gym picked), not
        inherently malicious, and plenty of endpoints (MyGymsView,
        OrganizationCreateView, TokenReissueView...) don't need a gym at
        all. The actual access control is unaffected — it's enforced
        downstream by request.gym being None (TenantQuerySet.for_gym /
        TenantViewSet return nothing; views that require a gym already
        check request.gym is None themselves) and by RLS using an empty
        app.gym_ids either way.
        """
        raw_gym_id = request.META.get(GYM_HEADER)
        if not raw_gym_id:
            return None, None

        try:
            gym_id = uuid.UUID(raw_gym_id)
        except ValueError:
            return None, None

        from accounts.models import StaffRole
        from core.context import system_context
        from gyms.models import Gym

        # Resolving *which* gym to scope to inherently requires seeing across
        # tenants — app.gym_ids isn't set yet, so RLS would block this query
        # otherwise. See core.context.system_context's docstring.
        with system_context():
            roles = list(
                StaffRole.objects.filter(user=user, is_active=True)
                .filter(Q(gym_id=gym_id) | Q(gym__isnull=True, org__gyms__id=gym_id))
                .values_list("role", flat=True)
            )
            if not roles:
                return None, None

            try:
                gym = Gym.objects.get(pk=gym_id)
            except Gym.DoesNotExist:
                return None, None

        role = max(roles, key=lambda r: ROLE_RANK.get(r, -1))
        return gym, role
