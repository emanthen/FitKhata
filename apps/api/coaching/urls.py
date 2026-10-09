from django.urls import path
from rest_framework.routers import DefaultRouter

from coaching.views import (
    BodyMeasurementViewSet,
    ClassBookingViewSet,
    ClassScheduleViewSet,
    ClientProfileViewSet,
    CoachingReportViewSet,
    DietLogViewSet,
    DietPlanViewSet,
    ExerciseViewSet,
    FoodItemViewSet,
    MemberBookingCancelView,
    MemberClassBookView,
    MemberClassListView,
    MemberCoachingReportsView,
    MemberNextClassView,
    MemberPlanView,
    MemberQuickLogView,
    OwnerCoachingInsightsView,
    PTPackViewSet,
    PTSessionViewSet,
    TrainerDashboardView,
    WorkoutLogViewSet,
    WorkoutPlanViewSet,
)

router = DefaultRouter()
router.register("coaching/exercises", ExerciseViewSet, basename="exercise")
router.register("coaching/food-items", FoodItemViewSet, basename="food-item")
router.register("coaching/client-profiles", ClientProfileViewSet, basename="client-profile")
router.register("coaching/measurements", BodyMeasurementViewSet, basename="body-measurement")
router.register("coaching/diet-logs", DietLogViewSet, basename="diet-log")
router.register("coaching/workout-plans", WorkoutPlanViewSet, basename="workout-plan")
router.register("coaching/diet-plans", DietPlanViewSet, basename="diet-plan")
router.register("coaching/workout-logs", WorkoutLogViewSet, basename="workout-log")
router.register("coaching/pt-packs", PTPackViewSet, basename="pt-pack")
router.register("coaching/pt-sessions", PTSessionViewSet, basename="pt-session")
router.register("coaching/classes", ClassScheduleViewSet, basename="class-schedule")
router.register("coaching/bookings", ClassBookingViewSet, basename="class-booking")
router.register("coaching/reports", CoachingReportViewSet, basename="coaching-report")

urlpatterns = [
    path("coaching/dashboard", TrainerDashboardView.as_view(), name="coaching-trainer-dashboard"),
    path("coaching/insights", OwnerCoachingInsightsView.as_view(), name="coaching-owner-insights"),
    path(
        "m/pass/<str:token>/coaching/reports",
        MemberCoachingReportsView.as_view(),
        name="member-coaching-reports",
    ),
    path(
        "m/pass/<str:token>/coaching/log",
        MemberQuickLogView.as_view(),
        name="member-coaching-log",
    ),
    path(
        "m/pass/<str:token>/coaching/plan",
        MemberPlanView.as_view(),
        name="member-coaching-plan",
    ),
    path(
        "m/pass/<str:token>/next-class",
        MemberNextClassView.as_view(),
        name="member-next-class",
    ),
    path(
        "m/pass/<str:token>/classes",
        MemberClassListView.as_view(),
        name="member-class-list",
    ),
    path(
        "m/pass/<str:token>/classes/<str:schedule_id>/book",
        MemberClassBookView.as_view(),
        name="member-class-book",
    ),
    path(
        "m/pass/<str:token>/bookings/<str:booking_id>/cancel",
        MemberBookingCancelView.as_view(),
        name="member-booking-cancel",
    ),
    *router.urls,
]
