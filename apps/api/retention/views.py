from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from django.core import signing
from django.db.models import Sum
from django.shortcuts import get_object_or_404
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsFrontDeskOrAbove, IsManagerOrAbove
from attendance.views import MEMBER_PASS_MAX_AGE, MEMBER_PASS_SALT
from core.context import system_context
from core.viewsets import TenantQuerysetMixin
from members.models import Member, Membership, PromoCode
from retention.models import Campaign, FreezeRequest, MembershipFreeze, RetentionCall
from retention.serializers import (
    CampaignSerializer,
    CompleteCallSerializer,
    FreezeRangeSerializer,
    FreezeRequestSerializer,
    IndividualFreezeSerializer,
    MemberFreezeRequestCreateSerializer,
    MembershipFreezeSerializer,
    RetentionCallSerializer,
    SendCampaignSerializer,
)
from retention.services import (
    MaxFreezeDaysExceeded,
    apply_individual_freeze,
    approve_freeze_request,
    complete_call,
    confirm_bulk_freeze,
    preview_bulk_freeze,
    recompute_campaign_conversions,
    reject_freeze_request,
    request_freeze,
    revert_freeze_batch,
    send_campaign,
)


class RetentionCallViewSet(
    TenantQuerysetMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    """FR-5.4/5.5: the Morning Call Queue. Read + the controlled `complete`
    action only -- outcome/completed_at are never set by a raw PATCH, so a
    queue item literally cannot clear without an outcome.
    """

    serializer_class = RetentionCallSerializer
    permission_classes = [permissions.IsAuthenticated, IsFrontDeskOrAbove]
    queryset = RetentionCall.objects.select_related("member")

    def get_queryset(self):
        qs = super().get_queryset()
        queue_date = self.request.query_params.get("queue_date", date.today().isoformat())
        qs = qs.filter(queue_date=queue_date)
        if self.request.query_params.get("include_completed") != "true":
            qs = qs.filter(completed_at__isnull=True)
        return qs.order_by("member__full_name")

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        call = self.get_object()
        serializer = CompleteCallSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        call = complete_call(
            call,
            outcome=data["outcome"],
            call_back_on=data.get("call_back_on"),
            notes=data.get("notes", ""),
        )
        return Response(RetentionCallSerializer(call).data)


class MembershipFreezeViewSet(TenantQuerysetMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    """FR-5.8/5.9: freeze history (read-only) -- actual freezing happens
    through the standalone views below, which enforce max_freeze_days and
    batch semantics that don't fit a plain create().
    """

    serializer_class = MembershipFreezeSerializer
    permission_classes = [permissions.IsAuthenticated, IsManagerOrAbove]
    queryset = MembershipFreeze.objects.select_related("membership__member")

    def get_queryset(self):
        return super().get_queryset().order_by("-created_at")


class FreezePreviewView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsManagerOrAbove]

    def post(self, request):
        if request.gym is None:
            return Response({"detail": "X-Gym-Id header is required."}, status=400)
        serializer = FreezeRangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        rows = preview_bulk_freeze(request.gym, data["start_date"], data["end_date"])
        return Response(
            {
                "count": len(rows),
                "rows": [
                    {
                        "member_id": row.member_id,
                        "member_name": row.member_name,
                        "membership_id": row.membership_id,
                        "previous_expiry": row.previous_expiry.isoformat(),
                        "new_expiry": row.new_expiry.isoformat(),
                        "would_exceed_max": row.would_exceed_max,
                    }
                    for row in rows
                ],
            }
        )


class FreezeBulkConfirmView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsManagerOrAbove]

    def post(self, request):
        if request.gym is None:
            return Response({"detail": "X-Gym-Id header is required."}, status=400)
        serializer = FreezeRangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        batch_id = confirm_bulk_freeze(
            request.gym, data["start_date"], data["end_date"], data["reason"], actor=request.user
        )
        return Response({"batch_id": str(batch_id)}, status=status.HTTP_201_CREATED)


class FreezeIndividualView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsManagerOrAbove]

    def post(self, request):
        if request.gym is None:
            return Response({"detail": "X-Gym-Id header is required."}, status=400)
        serializer = IndividualFreezeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        membership = get_object_or_404(
            Membership, pk=data["membership_id"], gym=request.gym
        )
        try:
            freeze = apply_individual_freeze(
                membership,
                data["start_date"],
                data["end_date"],
                data["reason"],
                actor=request.user,
                fee_npr=data.get("fee_npr", Decimal("0")),
            )
        except MaxFreezeDaysExceeded as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response(MembershipFreezeSerializer(freeze).data, status=status.HTTP_201_CREATED)


class FreezeBatchRevertView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsManagerOrAbove]

    def post(self, request, batch_id: str):
        if request.gym is None:
            return Response({"detail": "X-Gym-Id header is required."}, status=400)
        count = revert_freeze_batch(uuid.UUID(batch_id), request.gym, actor=request.user)
        if count == 0:
            return Response({"detail": "No active freezes found for this batch."}, status=404)
        return Response({"reverted": count})


class FreezeRequestViewSet(TenantQuerysetMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    """FR-8.6: the manager-facing approval queue for member-initiated
    freeze requests. Mutation happens only through the two controlled
    actions below -- same rule-7 shape as MembershipFreezeViewSet's sibling
    standalone apply views.
    """

    serializer_class = FreezeRequestSerializer
    permission_classes = [permissions.IsAuthenticated, IsManagerOrAbove]
    queryset = FreezeRequest.objects.select_related("member", "membership")

    def get_queryset(self):
        qs = super().get_queryset()
        status_filter = self.request.query_params.get("status", FreezeRequest.Status.PENDING)
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs.order_by("-created_at")

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        freeze_request = self.get_object()
        try:
            freeze_request = approve_freeze_request(freeze_request, actor=request.user)
        except MaxFreezeDaysExceeded as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response(FreezeRequestSerializer(freeze_request).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        freeze_request = self.get_object()
        freeze_request = reject_freeze_request(freeze_request, actor=request.user)
        return Response(FreezeRequestSerializer(freeze_request).data)


class MemberFreezeRequestCreateView(APIView):
    """Member-facing (pass-token authenticated): submit a freeze request
    for a manager to review -- never applies a freeze directly.
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request, token: str):
        try:
            data = signing.loads(token, salt=MEMBER_PASS_SALT, max_age=MEMBER_PASS_MAX_AGE)
        except signing.SignatureExpired:
            return Response({"detail": "This pass link has expired."}, status=400)
        except signing.BadSignature:
            return Response({"detail": "Invalid pass link."}, status=400)

        serializer = MemberFreezeRequestCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data

        with system_context():
            member = get_object_or_404(Member, pk=data["member_id"])
            membership = get_object_or_404(
                Membership, member=member, status=Membership.Status.ACTIVE
            )
            freeze_request = request_freeze(
                member,
                membership,
                payload["start_date"],
                payload["end_date"],
                payload["reason"],
            )
            return Response(
                FreezeRequestSerializer(freeze_request).data, status=status.HTTP_201_CREATED
            )


class CampaignViewSet(
    TenantQuerysetMixin, mixins.ListModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet
):
    """FR-5's winback campaigns: create == send (there's no separate draft
    state), list == history. IsManagerOrAbove -- this sends real SMS.
    """

    serializer_class = CampaignSerializer
    permission_classes = [permissions.IsAuthenticated, IsManagerOrAbove]
    queryset = Campaign.objects.all()

    def get_queryset(self):
        return super().get_queryset().order_by("-created_at")

    def create(self, request, *args, **kwargs):
        if request.gym is None:
            raise PermissionDenied("X-Gym-Id header is required.")
        serializer = SendCampaignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        promo = None
        if data.get("promo_code"):
            promo = get_object_or_404(PromoCode, gym=request.gym, code=data["promo_code"])

        campaign = send_campaign(request.gym, data["kind"], promo)
        return Response(CampaignSerializer(campaign).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def recompute(self, request, pk=None):
        campaign = get_object_or_404(Campaign, pk=pk, gym=request.gym)
        converted = recompute_campaign_conversions(campaign)
        return Response(CampaignSerializer(campaign).data | {"converted_count": converted})


class RetentionDashboardView(APIView):
    """FR-5.11: churn rate, saves this month, revenue protected."""

    permission_classes = [permissions.IsAuthenticated, IsFrontDeskOrAbove]

    def get(self, request):
        if request.gym is None:
            return Response({"detail": "X-Gym-Id header is required."}, status=400)
        gym = request.gym
        today = date.today()
        month_start = today.replace(day=1)

        active_at_month_start = Membership.objects.filter(
            gym=gym, status=Membership.Status.ACTIVE, start_date__lt=month_start
        ).values("member_id").distinct().count()

        churned_this_month = (
            Member.objects.filter(
                gym=gym,
                status__in=[Member.Status.EXPIRED, Member.Status.CANCELLED],
                updated_at__date__gte=month_start,
            ).count()
        )
        churn_rate = (churned_this_month / active_at_month_start) if active_at_month_start else 0.0

        saved_member_ids = list(
            RetentionCall.objects.filter(
                gym=gym,
                outcome=RetentionCall.Outcome.COMING_BACK,
                completed_at__date__gte=month_start,
            )
            .values_list("member_id", flat=True)
            .distinct()
        )
        saves_this_month = len(saved_member_ids)

        revenue_protected = Membership.objects.filter(
            gym=gym, member_id__in=saved_member_ids, status=Membership.Status.ACTIVE
        ).aggregate(total=Sum("plan__price_npr"))["total"] or Decimal("0.00")

        return Response(
            {
                "churn_rate": round(churn_rate, 4),
                "saves_this_month": saves_this_month,
                "revenue_protected_npr": str(revenue_protected),
            }
        )
