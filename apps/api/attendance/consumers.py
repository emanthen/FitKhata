"""Live occupancy + check-in feed (FR-3.10). Group gym_<id>; a check-in
broadcasts to it after attendance.services commits. Runs outside
TenantMiddleware entirely (only wired for the "http" protocol in
config/asgi.py) — auth and gym-membership are both checked here directly,
the same StaffRole shape TenantMiddleware's _resolve_gym uses, under
system_context() for the same cross-tenant-bootstrap reason.
"""

from __future__ import annotations

from datetime import timedelta
from urllib.parse import parse_qs

from asgiref.sync import async_to_sync
from channels.generic.websocket import JsonWebsocketConsumer
from django.utils import timezone
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import AccessToken

OCCUPANCY_WINDOW_MINUTES = 90


def group_name_for(gym_id: str) -> str:
    return f"gym_{gym_id}"


class GymFeedConsumer(JsonWebsocketConsumer):
    def connect(self) -> None:
        gym_id = str(self.scope["url_route"]["kwargs"]["gym_id"])
        token = self._token_from_query_string()
        user = self._authenticate(token)

        if user is None or not self._has_role_on_gym(user, gym_id):
            self.close(code=4401)
            return

        self.gym_id = gym_id
        self.group_name = group_name_for(gym_id)
        async_to_sync(self.channel_layer.group_add)(self.group_name, self.channel_name)
        self.accept()
        self.send_json({"type": "occupancy", "count": self._occupancy(gym_id)})

    def disconnect(self, code: int) -> None:
        group_name = getattr(self, "group_name", None)
        if group_name:
            async_to_sync(self.channel_layer.group_discard)(group_name, self.channel_name)

    def checkin_event(self, event: dict) -> None:
        """Handler name must match the `"type"` key sent to group_send —
        attendance.services sends {"type": "checkin.event", ...}, and
        Channels maps dots to underscores for the handler method name.
        """
        self.send_json(event["payload"])

    def _token_from_query_string(self) -> str | None:
        qs = parse_qs(self.scope["query_string"].decode("utf-8"))
        values = qs.get("token")
        return values[0] if values else None

    def _authenticate(self, token: str | None):
        if not token:
            return None
        try:
            # AccessToken's type hint claims `token: Token | None`, but its
            # own body passes it straight to token_backend.decode(), which
            # wants the raw encoded string — that's genuinely how every
            # caller (including SimpleJWT's own JWTAuthentication) uses it.
            validated = AccessToken(token)  # type: ignore[arg-type]
            return JWTAuthentication().get_user(validated)
        except (InvalidToken, TokenError):
            return None

    def _has_role_on_gym(self, user, gym_id: str) -> bool:
        from django.db.models import Q

        from accounts.models import StaffRole
        from core.context import system_context

        with system_context():
            return StaffRole.objects.filter(user=user, is_active=True).filter(
                Q(gym_id=gym_id) | Q(gym__isnull=True, org__gyms__id=gym_id)
            ).exists()

    def _occupancy(self, gym_id: str) -> int:
        from attendance.models import Attendance
        from core.context import system_context

        since = timezone.now() - timedelta(minutes=OCCUPANCY_WINDOW_MINUTES)
        with system_context():
            return Attendance.objects.filter(gym_id=gym_id, check_in_at__gte=since).count()
