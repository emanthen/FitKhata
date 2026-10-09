from __future__ import annotations

from datetime import date

from django.core import signing
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsFrontDeskOrAbove, IsManagerOrAbove, IsOwner, IsTrainer
from attendance.views import MEMBER_PASS_MAX_AGE, MEMBER_PASS_SALT
from coaching.models import (
    BodyMeasurement,
    ClassBooking,
    ClassSchedule,
    ClientProfile,
    CoachingReport,
    DietLog,
    DietPlan,
    Exercise,
    FoodItem,
    PTPack,
    PTSession,
    WorkoutLog,
    WorkoutPlan,
)
from coaching.serializers import (
    BodyMeasurementSerializer,
    ClassBookingSerializer,
    ClassScheduleSerializer,
    ClientProfileSerializer,
    CoachingReportSerializer,
    DietLogSerializer,
    DietPlanSerializer,
    ExerciseSerializer,
    FoodItemSerializer,
    PTPackSerializer,
    PTSessionSerializer,
    RejectReportSerializer,
    WorkoutLogSerializer,
    WorkoutPlanSerializer,
)
from coaching.services import (
    AlreadyBooked,
    approve_coaching_report,
    book_class,
    cancel_booking,
    log_protein_intake,
    log_workout,
    record_measurement,
    record_pt_attendance,
    reject_coaching_report,
)
from core.context import system_context
from core.viewsets import TenantQuerysetMixin, TenantViewSet
from members.models import Member

_MANAGER_RANK = {"owner": 3, "manager": 2}


def _is_manager_or_above(request) -> bool:
    return request.role in _MANAGER_RANK


def _member_from_pass_token(token: str):
    try:
        data = signing.loads(token, salt=MEMBER_PASS_SALT, max_age=MEMBER_PASS_MAX_AGE)
    except signing.SignatureExpired:
        return None, Response({"detail": "This pass link has expired."}, status=400)
    except signing.BadSignature:
        return None, Response({"detail": "Invalid pass link."}, status=400)
    with system_context():
        member = get_object_or_404(Member, pk=data["member_id"])
    return member, None


# --- Global catalogs (read-only, no tenant scoping) --------------------------


class ExerciseViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = ExerciseSerializer
    permission_classes = [permissions.AllowAny]
    queryset = Exercise.objects.filter(is_active=True).order_by("muscle_group", "name_en")
    filterset_fields = ["muscle_group", "equipment"]


class FoodItemViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = FoodItemSerializer
    permission_classes = [permissions.AllowAny]
    queryset = FoodItem.objects.all().order_by("name_en")


# --- Client profiles ----------------------------------------------------------


class ClientProfileViewSet(TenantViewSet):
    """Trainers see only their own clients; manager+ see every client at
    this gym. IsTrainer is an exact-role match (not hierarchical, unlike
    IsManagerOrAbove) — so both checks are needed in permission_classes.
    """

    serializer_class = ClientProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = ClientProfile.objects.select_related("member")

    def get_queryset(self):
        qs = super().get_queryset()
        if _is_manager_or_above(self.request):
            return qs
        if self.request.role == "trainer":
            return qs.filter(trainer=self.request.user)
        return qs.none()

    @action(detail=True, methods=["get"])
    def progress(self, request, pk=None):
        """Goal/attendance progress for this client's web profile page —
        reuses the same tested coaching/domain/progress.py formulas
        ai.py's weekly report uses, just without the AI/flags machinery.
        """
        from datetime import timedelta

        from attendance.models import Attendance
        from coaching.domain.progress import attendance_pct, goal_progress_pct
        from coaching.models import BodyMeasurement
        from coaching.services import EXPECTED_VISITS_PER_WEEK

        profile = self.get_object()
        today = date.today()
        window_start = today - timedelta(weeks=4)

        latest = (
            BodyMeasurement.objects.filter(member=profile.member).order_by("-measured_on").first()
        )
        current_weight = float(latest.weight_kg) if latest else float(profile.starting_weight_kg)

        visits = (
            Attendance.objects.filter(
                member=profile.member,
                check_in_at__date__gte=window_start,
                check_in_at__date__lte=today,
            )
            .values_list("check_in_at__date", flat=True)
            .distinct()
            .count()
        )
        expected = EXPECTED_VISITS_PER_WEEK * 4

        return Response(
            {
                "goal_progress_pct": goal_progress_pct(
                    float(profile.starting_weight_kg),
                    current_weight,
                    float(profile.target_weight_kg),
                ),
                "attendance_pct": attendance_pct(visits, expected),
                "current_weight_kg": current_weight,
            }
        )


# --- Body measurements ---------------------------------------------------------


class BodyMeasurementViewSet(
    TenantQuerysetMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = BodyMeasurementSerializer
    permission_classes = [permissions.IsAuthenticated, IsFrontDeskOrAbove]
    queryset = BodyMeasurement.objects.prefetch_related("photos").order_by("-measured_on")

    def get_queryset(self):
        qs = super().get_queryset()
        member_id = self.request.query_params.get("member")
        if member_id:
            qs = qs.filter(member_id=member_id)
        return qs

    def create(self, request, *args, **kwargs):
        if request.gym is None:
            raise PermissionDenied("X-Gym-Id header is required.")
        member = get_object_or_404(Member, pk=request.data.get("member"), gym=request.gym)
        photos = [(f, request.data.get("angle", "")) for f in request.FILES.getlist("photos")]
        measurement = record_measurement(
            member,
            measured_on=request.data["measured_on"],
            weight_kg=request.data["weight_kg"],
            body_fat_pct=request.data.get("body_fat_pct"),
            measurements=request.data.get("measurements"),
            photos=photos,
            actor=request.user,
        )
        return Response(BodyMeasurementSerializer(measurement).data, status=status.HTTP_201_CREATED)


class DietLogViewSet(
    TenantQuerysetMixin, mixins.ListModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet
):
    serializer_class = DietLogSerializer
    permission_classes = [permissions.IsAuthenticated, IsFrontDeskOrAbove]
    queryset = DietLog.objects.all().order_by("-logged_on")

    def create(self, request, *args, **kwargs):
        if request.gym is None:
            raise PermissionDenied("X-Gym-Id header is required.")
        member = get_object_or_404(Member, pk=request.data.get("member"), gym=request.gym)
        entry = log_protein_intake(
            member,
            logged_on=request.data["logged_on"],
            protein_g=request.data["protein_g"],
            actor=request.user,
        )
        return Response(DietLogSerializer(entry).data, status=status.HTTP_201_CREATED)


# --- Plans + logs ---------------------------------------------------------------


class WorkoutPlanViewSet(TenantViewSet):
    serializer_class = WorkoutPlanSerializer
    permission_classes = [permissions.IsAuthenticated, IsFrontDeskOrAbove]
    queryset = WorkoutPlan.objects.all()

    def perform_create(self, serializer):
        if self.request.gym is None:
            raise PermissionDenied("X-Gym-Id header is required.")
        serializer.save(
            gym=self.request.gym, org=self.request.gym.org, created_by=self.request.user
        )


class DietPlanViewSet(TenantViewSet):
    serializer_class = DietPlanSerializer
    permission_classes = [permissions.IsAuthenticated, IsFrontDeskOrAbove]
    queryset = DietPlan.objects.all()

    def perform_create(self, serializer):
        if self.request.gym is None:
            raise PermissionDenied("X-Gym-Id header is required.")
        serializer.save(
            gym=self.request.gym, org=self.request.gym.org, created_by=self.request.user
        )


class WorkoutLogViewSet(
    TenantQuerysetMixin, mixins.ListModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet
):
    """The <=3-tap quick logger: POST {member, exercise, sets}."""

    serializer_class = WorkoutLogSerializer
    permission_classes = [permissions.IsAuthenticated, IsFrontDeskOrAbove]
    queryset = WorkoutLog.objects.select_related("exercise").order_by("-logged_on")

    def get_queryset(self):
        qs = super().get_queryset()
        member_id = self.request.query_params.get("member")
        if member_id:
            qs = qs.filter(member_id=member_id)
        return qs

    def create(self, request, *args, **kwargs):
        if request.gym is None:
            raise PermissionDenied("X-Gym-Id header is required.")
        member = get_object_or_404(Member, pk=request.data.get("member"), gym=request.gym)
        exercise = get_object_or_404(Exercise, pk=request.data.get("exercise"))
        log = log_workout(
            member,
            logged_on=request.data.get("logged_on", date.today().isoformat()),
            exercise=exercise,
            sets=request.data.get("sets", []),
            actor=request.user,
        )
        return Response(WorkoutLogSerializer(log).data, status=status.HTTP_201_CREATED)


# --- PT packs + sessions -------------------------------------------------------


class PTPackViewSet(TenantViewSet):
    serializer_class = PTPackSerializer
    permission_classes = [permissions.IsAuthenticated, IsFrontDeskOrAbove]
    queryset = PTPack.objects.all()


class PTSessionViewSet(TenantViewSet):
    serializer_class = PTSessionSerializer
    permission_classes = [permissions.IsAuthenticated, IsFrontDeskOrAbove]
    queryset = PTSession.objects.select_related("pack")

    @action(detail=True, methods=["post"])
    def mark_attended(self, request, pk=None):
        session = self.get_object()
        attended = bool(request.data.get("attended", True))
        session = record_pt_attendance(session, attended, actor=request.user)
        return Response(PTSessionSerializer(session).data)


# --- Classes + bookings ---------------------------------------------------------


class ClassScheduleViewSet(TenantViewSet):
    serializer_class = ClassScheduleSerializer
    permission_classes = [permissions.IsAuthenticated, IsFrontDeskOrAbove]
    queryset = ClassSchedule.objects.all().order_by("starts_at")


class ClassBookingViewSet(
    TenantQuerysetMixin, mixins.ListModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet
):
    serializer_class = ClassBookingSerializer
    permission_classes = [permissions.IsAuthenticated, IsFrontDeskOrAbove]
    queryset = ClassBooking.objects.select_related("member")

    def create(self, request, *args, **kwargs):
        if request.gym is None:
            raise PermissionDenied("X-Gym-Id header is required.")
        schedule = get_object_or_404(
            ClassSchedule, pk=request.data.get("class_schedule"), gym=request.gym
        )
        member = get_object_or_404(Member, pk=request.data.get("member"), gym=request.gym)
        try:
            booking = book_class(schedule, member, actor=request.user)
        except AlreadyBooked as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response(ClassBookingSerializer(booking).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        booking = self.get_object()
        booking = cancel_booking(booking, actor=request.user)
        return Response(ClassBookingSerializer(booking).data)


# --- Coaching reports (trainer approves before a member sees anything) -------


class CoachingReportViewSet(
    TenantQuerysetMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    serializer_class = CoachingReportSerializer
    permission_classes = [permissions.IsAuthenticated, IsFrontDeskOrAbove]
    queryset = CoachingReport.objects.select_related("member").order_by("-week_start")

    def get_queryset(self):
        qs = super().get_queryset()
        kind = self.request.query_params.get("kind")
        if kind:
            qs = qs.filter(kind=kind)
        status_filter = self.request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[permissions.IsAuthenticated, IsTrainer | IsManagerOrAbove],
    )
    def approve(self, request, pk=None):
        report = self.get_object()
        report = approve_coaching_report(report, actor=request.user)
        return Response(CoachingReportSerializer(report).data)

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[permissions.IsAuthenticated, IsTrainer | IsManagerOrAbove],
    )
    def reject(self, request, pk=None):
        report = self.get_object()
        serializer = RejectReportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        report = reject_coaching_report(
            report, actor=request.user, reason=serializer.validated_data["reason"]
        )
        return Response(CoachingReportSerializer(report).data)


class OwnerCoachingInsightsView(APIView):
    """Latest branch-level CoachingReport + month-to-date AI spend vs budget."""

    permission_classes = [permissions.IsAuthenticated, IsOwner]

    def get(self, request):
        if request.gym is None:
            return Response({"detail": "X-Gym-Id header is required."}, status=400)
        latest = (
            CoachingReport.objects.filter(gym=request.gym, kind=CoachingReport.Kind.BRANCH)
            .order_by("-week_start")
            .first()
        )
        from coaching.ai import _month_spend_npr

        budget = request.gym.settings.get("ai_budget_npr_monthly", 2000)
        spend = _month_spend_npr(request.gym)
        return Response(
            {
                "latest_branch_report": CoachingReportSerializer(latest).data if latest else None,
                "ai_budget_npr_monthly": budget,
                "ai_spend_npr_month_to_date": str(spend),
            }
        )


class TrainerDashboardView(APIView):
    """My clients, their active flags, and my pending approvals queue."""

    permission_classes = [permissions.IsAuthenticated, IsTrainer]

    def get(self, request):
        if request.gym is None:
            return Response({"detail": "X-Gym-Id header is required."}, status=400)
        clients = ClientProfile.objects.filter(
            gym=request.gym, trainer=request.user
        ).select_related("member")
        pending = CoachingReport.objects.filter(
            gym=request.gym,
            kind=CoachingReport.Kind.MEMBER,
            status=CoachingReport.Status.DRAFT,
            member__coaching_profile__trainer=request.user,
        )
        return Response(
            {
                "clients": ClientProfileSerializer(clients, many=True).data,
                "pending_approvals": CoachingReportSerializer(pending, many=True).data,
            }
        )


# --- Member-facing (token-authenticated) --------------------------------------


class MemberCoachingReportsView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, token: str):
        member, error = _member_from_pass_token(token)
        if error:
            return error
        with system_context():
            reports = CoachingReport.objects.filter(
                member=member,
                kind=CoachingReport.Kind.MEMBER,
                status=CoachingReport.Status.APPROVED,
            ).order_by("-week_start")
            return Response(CoachingReportSerializer(reports, many=True).data)


class MemberQuickLogView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, token: str):
        member, error = _member_from_pass_token(token)
        if error:
            return error
        with system_context():
            exercise = get_object_or_404(Exercise, pk=request.data.get("exercise"))
            log = log_workout(
                member,
                logged_on=request.data.get("logged_on", date.today().isoformat()),
                exercise=exercise,
                sets=request.data.get("sets", []),
            )
            return Response(WorkoutLogSerializer(log).data, status=status.HTTP_201_CREATED)


class MemberPlanView(APIView):
    """FR-8.5's "My plan" page: the member's own assigned workout/diet
    plan, sourced from their ClientProfile (if one exists yet — a member
    with no trainer-assigned profile just sees both as null).
    """

    permission_classes = [permissions.AllowAny]

    def get(self, request, token: str):
        member, error = _member_from_pass_token(token)
        if error:
            return error
        with system_context():
            profile = ClientProfile.objects.filter(member=member).first()
            return Response(
                {
                    "workout_plan": (
                        WorkoutPlanSerializer(profile.workout_plan).data
                        if profile and profile.workout_plan
                        else None
                    ),
                    "diet_plan": (
                        DietPlanSerializer(profile.diet_plan).data
                        if profile and profile.diet_plan
                        else None
                    ),
                }
            )


class MemberNextClassView(APIView):
    """FR-8.3's home-card "next class" line."""

    permission_classes = [permissions.AllowAny]

    def get(self, request, token: str):
        member, error = _member_from_pass_token(token)
        if error:
            return error
        with system_context():
            booking = (
                ClassBooking.objects.filter(
                    member=member,
                    status=ClassBooking.Status.BOOKED,
                    class_schedule__starts_at__gt=timezone.now(),
                )
                .select_related("class_schedule")
                .order_by("class_schedule__starts_at")
                .first()
            )
            if booking is None:
                return Response(None)
            return Response(
                {
                    "class_name": booking.class_schedule.name,
                    "starts_at": booking.class_schedule.starts_at,
                }
            )


class MemberClassListView(APIView):
    """FR-8.7: upcoming classes at the member's own gym, for booking."""

    permission_classes = [permissions.AllowAny]

    def get(self, request, token: str):
        member, error = _member_from_pass_token(token)
        if error:
            return error
        with system_context():
            schedules = ClassSchedule.objects.filter(
                gym=member.gym, starts_at__gt=timezone.now()
            ).order_by("starts_at")
            return Response(ClassScheduleSerializer(schedules, many=True).data)


class MemberClassBookView(APIView):
    """Never accepts a member_id from the request body -- the pass token
    is the only source of truth for which member is booking.
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request, token: str, schedule_id: str):
        member, error = _member_from_pass_token(token)
        if error:
            return error
        with system_context():
            schedule = get_object_or_404(ClassSchedule, pk=schedule_id, gym=member.gym)
            try:
                booking = book_class(schedule, member)
            except AlreadyBooked as exc:
                return Response({"detail": str(exc)}, status=400)
            return Response(ClassBookingSerializer(booking).data, status=status.HTTP_201_CREATED)


class MemberBookingCancelView(APIView):
    """404s (not 403) on another member's booking id -- same don't-reveal-
    it-exists reasoning as MemberInvoicePdfView.
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request, token: str, booking_id: str):
        member, error = _member_from_pass_token(token)
        if error:
            return error
        with system_context():
            booking = get_object_or_404(ClassBooking, pk=booking_id, member=member)
            booking = cancel_booking(booking)
            return Response(ClassBookingSerializer(booking).data)
