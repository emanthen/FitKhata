from __future__ import annotations

from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsOwner
from billing.models import Invoice
from members.models import Member, Membership
from publicapi.permissions import require_scope
from publicapi.serializers import (
    ApiKeyCreateSerializer,
    ApiKeySerializer,
    PublicInvoiceSerializer,
    PublicMemberSerializer,
    PublicMembershipSerializer,
    WebhookDeliverySerializer,
    WebhookSubscriptionCreateSerializer,
    WebhookSubscriptionSerializer,
)
from publicapi.services import (
    create_api_key,
    create_webhook_subscription,
    revoke_api_key,
)
from saas.decorators import requires_feature


def _rate_limit_key(group: str, request) -> str:
    api_key = getattr(request, "api_key", None)
    return str(api_key.pk) if api_key else "anonymous"


rate_limited = method_decorator(
    ratelimit(key=_rate_limit_key, rate="100/m", block=True), name="dispatch"
)


# --- FR-12.3: public read endpoints, API-key authenticated ----------------


@rate_limited
class PublicMemberListView(generics.ListAPIView):
    serializer_class = PublicMemberSerializer
    permission_classes = [require_scope("members:read")]

    def get_queryset(self):
        return Member.objects.filter(org=self.request.api_key.org)


@rate_limited
class PublicMembershipListView(generics.ListAPIView):
    serializer_class = PublicMembershipSerializer
    permission_classes = [require_scope("memberships:read")]

    def get_queryset(self):
        return Membership.objects.filter(org=self.request.api_key.org)


@rate_limited
class PublicInvoiceListView(generics.ListAPIView):
    serializer_class = PublicInvoiceSerializer
    permission_classes = [require_scope("invoices:read")]

    def get_queryset(self):
        return Invoice.objects.filter(org=self.request.api_key.org)


# --- Owner-facing management: create/revoke keys, manage webhooks ---------


class ApiKeyListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsOwner]

    @requires_feature("public_api")
    def get(self, request):
        from publicapi.models import ApiKey

        keys = ApiKey.objects.filter(org=request.gym.org, revoked_at__isnull=True)
        return Response(ApiKeySerializer(keys, many=True).data)

    @requires_feature("public_api")
    def post(self, request):
        serializer = ApiKeyCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        api_key, raw_key = create_api_key(
            request.gym.org,
            serializer.validated_data["name"],
            list(serializer.validated_data["scopes"]),
            actor=request.user,
        )
        return Response(
            {**ApiKeySerializer(api_key).data, "key": raw_key}, status=status.HTTP_201_CREATED
        )


class ApiKeyRevokeView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsOwner]

    @requires_feature("public_api")
    def post(self, request, pk):
        from django.shortcuts import get_object_or_404

        from publicapi.models import ApiKey

        api_key = get_object_or_404(ApiKey, pk=pk, org=request.gym.org)
        revoke_api_key(api_key, actor=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


class WebhookSubscriptionListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsOwner]

    @requires_feature("public_api")
    def get(self, request):
        from publicapi.models import WebhookSubscription

        subs = WebhookSubscription.objects.filter(org=request.gym.org)
        return Response(WebhookSubscriptionSerializer(subs, many=True).data)

    @requires_feature("public_api")
    def post(self, request):
        serializer = WebhookSubscriptionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        subscription = create_webhook_subscription(
            request.gym.org,
            serializer.validated_data["url"],
            list(serializer.validated_data["events"]),
            serializer.validated_data["secret"],
            actor=request.user,
        )
        return Response(
            WebhookSubscriptionSerializer(subscription).data, status=status.HTTP_201_CREATED
        )


class WebhookDeliveryListView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsOwner]

    @requires_feature("public_api")
    def get(self, request, pk):
        from django.shortcuts import get_object_or_404

        from publicapi.models import WebhookSubscription

        subscription = get_object_or_404(WebhookSubscription, pk=pk, org=request.gym.org)
        deliveries = subscription.deliveries.order_by("-created_at")[:100]
        return Response(WebhookDeliverySerializer(deliveries, many=True).data)
