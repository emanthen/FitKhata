from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.conf import settings
from django.core import signing
from django.db.models import Q, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsFrontDeskOrAbove, IsManagerOrAbove, IsOwner
from attendance.views import MEMBER_PASS_MAX_AGE, MEMBER_PASS_SALT
from core.context import system_context
from core.viewsets import TenantQuerysetMixin, TenantViewSet
from members.models import Member
from notifications.models import Announcement, Broadcast, Notification, PushSubscription, Template
from notifications.providers.whatsapp import verify_webhook_signature
from notifications.serializers import (
    AnnouncementSerializer,
    BroadcastEstimateSerializer,
    BroadcastSerializer,
    NotificationSerializer,
    SendBroadcastSerializer,
    TemplateSerializer,
)
from notifications.services import estimate_broadcast, send_broadcast


def _member_from_pass_token(token: str):
    """Same signed pass-link token as attendance.views.MemberPassView /
    billing.views's member-renewal family — already this app's proof of a
    member's identity for the PWA, no separate login needed.
    """
    try:
        data = signing.loads(token, salt=MEMBER_PASS_SALT, max_age=MEMBER_PASS_MAX_AGE)
    except signing.SignatureExpired:
        return None, Response({"detail": "This pass link has expired."}, status=400)
    except signing.BadSignature:
        return None, Response({"detail": "Invalid pass link."}, status=400)
    with system_context():
        member = get_object_or_404(Member, pk=data["member_id"])
    return member, None


class TemplateViewSet(viewsets.ModelViewSet):
    """FR-6.1's template editor. Only ever lists/edits the calling org's OWN
    override rows — the platform-default (org=NULL) catalog seeded by
    migrations/0003 is read via the separate `defaults` action, never
    editable here, so one org can't accidentally mutate every other org's
    fallback wording.
    """

    serializer_class = TemplateSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwner]
    queryset = Template.objects.filter(org__isnull=False)

    def get_queryset(self):
        if self.request.gym is None:
            return super().get_queryset().none()
        return super().get_queryset().filter(org=self.request.gym.org)

    def perform_create(self, serializer):
        if self.request.gym is None:
            raise PermissionDenied("X-Gym-Id header is required.")
        serializer.save(org=self.request.gym.org)

    @action(detail=False, methods=["get"])
    def defaults(self, request):
        """The platform catalog, for the editor's "here's the default
        wording" reference/live-preview — read-only, any key/channel/language.
        """
        qs = Template.objects.filter(org__isnull=True)
        key = request.query_params.get("key")
        if key:
            qs = qs.filter(key=key)
        return Response(TemplateSerializer(qs, many=True).data)


class NotificationViewSet(
    TenantQuerysetMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    """FR-6's delivery log — read-only, filterable by channel/status/member/date."""

    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated, IsFrontDeskOrAbove]
    queryset = Notification.objects.select_related("member")

    def get_queryset(self):
        qs = super().get_queryset().order_by("-created_at")
        params = self.request.query_params
        if params.get("channel"):
            qs = qs.filter(channel=params["channel"])
        if params.get("status"):
            qs = qs.filter(status=params["status"])
        if params.get("member"):
            qs = qs.filter(member_id=params["member"])
        if params.get("date_from"):
            qs = qs.filter(created_at__date__gte=params["date_from"])
        if params.get("date_to"):
            qs = qs.filter(created_at__date__lte=params["date_to"])
        return qs

    @action(detail=False, methods=["get"])
    def monthly_cost(self, request):
        if request.gym is None:
            return Response({"detail": "X-Gym-Id header is required."}, status=400)
        today = date.today()
        total = Notification.objects.filter(
            gym=request.gym, created_at__year=today.year, created_at__month=today.month
        ).aggregate(total=Sum("cost_npr"))["total"] or Decimal("0.00")
        return Response({"month": today.strftime("%Y-%m"), "cost_npr": str(total)})


# --- Broadcast (FR-6.4) ------------------------------------------------------


class BroadcastEstimateView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsManagerOrAbove]

    def post(self, request):
        if request.gym is None:
            return Response({"detail": "X-Gym-Id header is required."}, status=400)
        serializer = BroadcastEstimateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        count, cost = estimate_broadcast(
            request.gym, data["segment"], data.get("segment_value", ""), data["channel"]
        )
        return Response({"recipient_count": count, "cost_npr": str(cost)})


class BroadcastViewSet(
    TenantQuerysetMixin, mixins.ListModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet
):
    """Create == send (FR-6.4) — the composer already called
    BroadcastEstimateView for its preview before this is ever hit.
    """

    serializer_class = BroadcastSerializer
    permission_classes = [permissions.IsAuthenticated, IsManagerOrAbove]
    queryset = Broadcast.objects.all()

    def get_queryset(self):
        return super().get_queryset().order_by("-created_at")

    def create(self, request, *args, **kwargs):
        if request.gym is None:
            raise PermissionDenied("X-Gym-Id header is required.")
        serializer = SendBroadcastSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        broadcast = send_broadcast(
            request.gym,
            data["segment"],
            data.get("segment_value", ""),
            data["channel"],
            data["body_ne"],
            data["body_en"],
            actor=request.user,
        )
        return Response(BroadcastSerializer(broadcast).data, status=status.HTTP_201_CREATED)


# --- Announcements (FR-6.7) --------------------------------------------------


class AnnouncementViewSet(TenantViewSet):
    serializer_class = AnnouncementSerializer
    permission_classes = [permissions.IsAuthenticated, IsManagerOrAbove]
    queryset = Announcement.objects.all()

    def get_queryset(self):
        return super().get_queryset().order_by("-created_at")

    def perform_create(self, serializer):
        if self.request.gym is None:
            raise PermissionDenied("X-Gym-Id header is required.")
        serializer.save(
            gym=self.request.gym, org=self.request.gym.org, created_by=self.request.user
        )


class MemberAnnouncementsView(APIView):
    """What the Member PWA's announcement banner reads — unauthenticated,
    the signed pass token is the proof (same shape as MemberPassView).
    """

    permission_classes = [permissions.AllowAny]

    def get(self, request, token: str):
        member, error = _member_from_pass_token(token)
        if error:
            return error

        now = timezone.now()
        with system_context():
            announcements = (
                Announcement.objects.filter(gym=member.gym, is_active=True)
                .filter(Q(starts_at__isnull=True) | Q(starts_at__lte=now))
                .filter(Q(ends_at__isnull=True) | Q(ends_at__gte=now))
                .order_by("-created_at")
            )
            data = [
                {
                    "id": a.pk,
                    "title": a.title,
                    "body": a.body_ne if member.language == Member.Language.NEPALI else a.body_en,
                }
                for a in announcements
            ]
        return Response(data)


class MemberPushSubscribeView(APIView):
    """Registers a Web Push subscription for the Member PWA."""

    permission_classes = [permissions.AllowAny]

    def post(self, request, token: str):
        member, error = _member_from_pass_token(token)
        if error:
            return error

        endpoint = request.data.get("endpoint")
        keys = request.data.get("keys")
        if not endpoint or not keys:
            return Response({"detail": "endpoint and keys are required."}, status=400)

        with system_context():
            PushSubscription.objects.update_or_create(
                endpoint=endpoint,
                defaults={
                    "org": member.org,
                    "gym": member.gym,
                    "member": member,
                    "keys": keys,
                    "user_agent": request.data.get("user_agent", ""),
                },
            )
        return Response({"subscribed": True}, status=status.HTTP_201_CREATED)


# --- WhatsApp webhook (FR-6.5) -----------------------------------------------


class WhatsAppWebhookView(APIView):
    """Meta's webhook for the Cloud API — verified via Meta's own
    verify-token handshake (GET) and X-Hub-Signature-256 (POST). AllowAny:
    Meta can't send our auth headers, the signature IS the authentication.
    """

    permission_classes = [permissions.AllowAny]

    def get(self, request):
        if request.query_params.get("hub.verify_token") == settings.WHATSAPP_WEBHOOK_VERIFY_TOKEN:
            # text/plain, not Django's HttpResponse default of text/html: this
            # echoes back a client-supplied query param verbatim per Meta's
            # handshake protocol -- an explicit non-HTML content-type is what
            # actually stops a browser from ever executing it as a script,
            # not the verify-token gate above. semgrep's reflected-data-
            # httpresponse rule can't model that a non-HTML content_type
            # closes the XSS vector regardless of payload -- suppressed with
            # that reasoning on record, not blindly.
            challenge = request.query_params.get("hub.challenge", "")  # nosemgrep
            return HttpResponse(challenge, content_type="text/plain")
        return Response(status=status.HTTP_403_FORBIDDEN)

    def post(self, request):
        if not verify_webhook_signature(request.body, request.headers.get("X-Hub-Signature-256")):
            return Response(status=status.HTTP_403_FORBIDDEN)

        with system_context():
            for entry in request.data.get("entry", []):
                for change in entry.get("changes", []):
                    for status_update in change.get("value", {}).get("statuses", []):
                        notification = Notification.objects.filter(
                            provider_ref=status_update.get("id")
                        ).first()
                        if notification is None:
                            continue
                        if status_update.get("status") == "delivered":
                            notification.status = Notification.Status.DELIVERED
                            notification.delivered_at = timezone.now()
                            notification.save(update_fields=["status", "delivered_at"])
        return Response(status=status.HTTP_200_OK)
