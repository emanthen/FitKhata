from __future__ import annotations

from datetime import date

from django.contrib.postgres.search import TrigramSimilarity
from django.core import signing
from django.core.files.storage import default_storage
from django.db.models import Q
from django.db.models.functions import Greatest
from django.shortcuts import get_object_or_404
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.pagination import CursorPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsFrontDeskOrAbove, IsManagerOrAbove
from attendance.views import MEMBER_PASS_MAX_AGE, MEMBER_PASS_SALT
from core.context import system_context
from core.viewsets import TenantQuerysetMixin, TenantViewSet
from gyms.models import Gym
from members.models import AddOn, ImportJob, Member, Membership, Plan, PromoCode, Waiver
from members.serializers import (
    AddOnSerializer,
    ImportJobSerializer,
    MemberFeedbackCreateSerializer,
    MemberFeedbackSerializer,
    MemberSerializer,
    MembershipSerializer,
    PlanSerializer,
    PromoCodeSerializer,
    SellMembershipSerializer,
    TransferMemberSerializer,
    WaiverSerializer,
)
from members.services import register_member, sell_membership, submit_feedback, transfer_member
from members.tasks import import_members_task
from saas.services import MemberLimitExceeded

SEARCH_RESULT_LIMIT = 50


class MemberCursorPagination(CursorPagination):
    ordering = "-created_at"
    page_size = 25


class MemberViewSet(TenantViewSet):
    serializer_class = MemberSerializer
    permission_classes = [permissions.IsAuthenticated, IsFrontDeskOrAbove]
    queryset = Member.objects.all()
    pagination_class = MemberCursorPagination
    filterset_fields = ["status", "risk_state"]

    def get_queryset(self):
        qs = super().get_queryset()
        tag = self.request.query_params.get("tag")
        if tag:
            qs = qs.filter(tags__contains=[tag])
        plan_id = self.request.query_params.get("plan")
        if plan_id:
            qs = qs.filter(memberships__plan_id=plan_id).distinct()
        return qs

    def list(self, request, *args, **kwargs):
        """?q= bypasses cursor pagination entirely — trigram-ranked search
        is "find this one member", not infinite-scroll browsing, and mixing
        a relevance ordering with cursor pagination's stable-ordering
        requirement is more complexity than this needs.
        """
        q = request.query_params.get("q", "").strip()
        if not q:
            return super().list(request, *args, **kwargs)

        # Filter with the `%` operator (trigram_similar) first — that's the
        # operator pg_trgm's GIN index actually accelerates. Using
        # TrigramSimilarity's similarity() function directly in a WHERE/
        # HAVING clause (the "obvious" Django way) does NOT hit the index —
        # it forces a sequential scan computing similarity for every row,
        # ~400ms over 10k rows instead of the <300ms acceptance target.
        # Keep TrigramSimilarity only for ranking the now-much-smaller
        # matched set.
        queryset = (
            self.filter_queryset(self.get_queryset())
            .filter(
                Q(full_name__trigram_similar=q)
                | Q(phone__trigram_similar=q)
                | Q(member_code__trigram_similar=q)
            )
            .annotate(
                similarity=Greatest(
                    TrigramSimilarity("full_name", q),
                    TrigramSimilarity("phone", q),
                    TrigramSimilarity("member_code", q),
                )
            )
            .order_by("-similarity")[:SEARCH_RESULT_LIMIT]
        )
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def perform_create(self, serializer):
        if self.request.gym is None:
            raise PermissionDenied("X-Gym-Id header is required.")
        try:
            serializer.instance = register_member(
                self.request.gym, actor=self.request.user, **serializer.validated_data
            )
        except MemberLimitExceeded as exc:
            raise PermissionDenied(str(exc)) from exc

    @action(detail=True, methods=["post"])
    def sell(self, request, pk=None):
        member = self.get_object()
        serializer = SellMembershipSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        promo = None
        promo_code = data.get("promo_code", "").strip()
        if promo_code:
            promo = get_object_or_404(PromoCode, gym=request.gym, code=promo_code)

        membership = sell_membership(
            member,
            data["plan_id"],
            actor=request.user,
            promo=promo,
            addons=list(data.get("addon_ids", [])),
        )
        return Response(
            MembershipSerializer(membership).data, status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=["post"])
    def transfer(self, request, pk=None):
        member = self.get_object()
        serializer = TransferMemberSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # The target gym is, by definition, a different gym than the one
        # request.gym/RLS is currently scoped to — the same bootstrapping
        # case core.middleware has for resolving X-Gym-Id in the first
        # place (see core/middleware.py's docstring).
        with system_context():
            new_gym = get_object_or_404(Gym, pk=serializer.validated_data["gym_id"])

        # Not refresh_from_db(): after the transfer this member is, by
        # design, no longer visible under the *source* gym's RLS scope that
        # this request is still running under — the in-memory object
        # transfer_member() already updated is what we have to respond with.
        member = transfer_member(member, new_gym, actor=request.user)
        return Response(MemberSerializer(member).data)


class PlanViewSet(TenantViewSet):
    serializer_class = PlanSerializer
    permission_classes = [permissions.IsAuthenticated, IsManagerOrAbove]
    queryset = Plan.objects.all()


class AddOnViewSet(TenantViewSet):
    serializer_class = AddOnSerializer
    permission_classes = [permissions.IsAuthenticated, IsManagerOrAbove]
    queryset = AddOn.objects.all()


class PromoCodeViewSet(TenantViewSet):
    serializer_class = PromoCodeSerializer
    permission_classes = [permissions.IsAuthenticated, IsManagerOrAbove]
    queryset = PromoCode.objects.all()


class WaiverViewSet(TenantViewSet):
    """Create + read only — a signed waiver is never edited, only replaced
    by signing a new one (matches rule 7's never-edit-in-place pattern for
    sensitive records, applied here even though Waiver isn't money).
    """

    http_method_names = ["get", "post", "head", "options"]
    serializer_class = WaiverSerializer
    permission_classes = [permissions.IsAuthenticated, IsFrontDeskOrAbove]
    queryset = Waiver.objects.all()

    def get_queryset(self):
        qs = super().get_queryset()
        member_id = self.request.query_params.get("member")
        if member_id:
            qs = qs.filter(member_id=member_id)
        return qs

    def perform_create(self, serializer):
        if self.request.gym is None:
            raise PermissionDenied("X-Gym-Id header is required.")
        serializer.save(
            gym=self.request.gym, org=self.request.gym.org, ip=self.request.META.get("REMOTE_ADDR")
        )


class MembershipViewSet(TenantQuerysetMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = MembershipSerializer
    permission_classes = [permissions.IsAuthenticated, IsFrontDeskOrAbove]
    queryset = Membership.objects.all()

    def get_queryset(self):
        qs = super().get_queryset()
        member_id = self.request.query_params.get("member")
        if member_id:
            qs = qs.filter(member_id=member_id)
        return qs


class MemberMembershipStatusView(APIView):
    """FR-8.3's home status card: current plan, expiry date (AD -- the
    client converts to BS via lib/bs-calendar.ts, same as every other
    BS-display spot in the Member PWA) and days left.
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
            membership = (
                Membership.objects.filter(member=member).order_by("-expiry_date").first()
            )
            if membership is None:
                return Response(None)
            days_left = (membership.expiry_date - date.today()).days
            return Response(
                {
                    "plan_name": membership.plan.name,
                    "expiry_date": membership.expiry_date.isoformat(),
                    "days_left": days_left,
                    "status": membership.status,
                }
            )


class MemberFeedbackCreateView(APIView):
    """FR-8.6: the Member PWA's feedback/complaint form. Same pass-token
    auth as the rest of the m/pass/<token>/... family.
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request, token: str):
        try:
            data = signing.loads(token, salt=MEMBER_PASS_SALT, max_age=MEMBER_PASS_MAX_AGE)
        except signing.SignatureExpired:
            return Response({"detail": "This pass link has expired."}, status=400)
        except signing.BadSignature:
            return Response({"detail": "Invalid pass link."}, status=400)

        serializer = MemberFeedbackCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        with system_context():
            member = get_object_or_404(Member, pk=data["member_id"])
            feedback = submit_feedback(member, serializer.validated_data["message"])
            return Response(
                MemberFeedbackSerializer(feedback).data, status=status.HTTP_201_CREATED
            )


class ImportMembersView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsManagerOrAbove]

    def post(self, request):
        if request.gym is None:
            return Response({"detail": "X-Gym-Id header is required."}, status=400)
        upload = request.FILES.get("file")
        if upload is None:
            return Response({"detail": "A file upload is required."}, status=400)

        job = ImportJob.objects.create(
            org=request.gym.org, gym=request.gym, total_rows=0, uploaded_by=request.user
        )
        dest = f"members/{request.gym.pk}/imports/{job.pk}/{upload.name}"
        file_path = default_storage.save(dest, upload)
        import_members_task.delay(
            str(job.pk), str(request.gym.pk), file_path, str(request.user.pk)
        )
        return Response(ImportJobSerializer(job).data, status=status.HTTP_202_ACCEPTED)


class ImportJobStatusView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsManagerOrAbove]

    def get(self, request, job_id):
        if request.gym is None:
            return Response({"detail": "X-Gym-Id header is required."}, status=400)
        job = get_object_or_404(ImportJob.objects.for_gym(request.gym), pk=job_id)
        return Response(ImportJobSerializer(job).data)
