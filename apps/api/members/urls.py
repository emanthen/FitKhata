from django.urls import path
from rest_framework.routers import DefaultRouter

from members.views import (
    AddOnViewSet,
    ImportJobStatusView,
    ImportMembersView,
    MembershipViewSet,
    MemberViewSet,
    PlanViewSet,
    PromoCodeViewSet,
    WaiverViewSet,
)

router = DefaultRouter()
router.register("members", MemberViewSet, basename="member")
router.register("plans", PlanViewSet, basename="plan")
router.register("addons", AddOnViewSet, basename="addon")
router.register("promo-codes", PromoCodeViewSet, basename="promo-code")
router.register("memberships", MembershipViewSet, basename="membership")
router.register("waivers", WaiverViewSet, basename="waiver")

urlpatterns = [
    path("members/import", ImportMembersView.as_view(), name="members-import"),
    path(
        "members/import/<uuid:job_id>",
        ImportJobStatusView.as_view(),
        name="members-import-status",
    ),
    *router.urls,
]
