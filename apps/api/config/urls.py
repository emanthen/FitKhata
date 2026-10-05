from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.routers import DefaultRouter

from accounts.views import MyGymsView, StaffRoleViewSet
from billing.views import InvoiceViewSet
from core.views import healthz, readyz
from gyms.views import GymCreateView, OrganizationCreateView

router = DefaultRouter()
router.register("staff-roles", StaffRoleViewSet, basename="staff-role")
router.register("invoices", InvoiceViewSet, basename="invoice")

urlpatterns = [
    path("admin/", admin.site.urls),
    path("healthz", healthz),
    path("readyz", readyz),
    path("api/v1/schema", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
    path("api/v1/auth/", include("accounts.urls")),
    path("api/v1/orgs", OrganizationCreateView.as_view(), name="orgs-create"),
    path("api/v1/gyms", GymCreateView.as_view(), name="gyms-create"),
    path("api/v1/gyms/mine", MyGymsView.as_view(), name="gyms-mine"),
    path("api/v1/", include(router.urls)),
    path("api/v1/", include("members.urls")),
    path("api/v1/", include("attendance.urls")),
]
