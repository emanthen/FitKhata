from django.urls import path
from rest_framework.routers import DefaultRouter

from notifications.views import (
    AnnouncementViewSet,
    BroadcastEstimateView,
    BroadcastViewSet,
    MemberAnnouncementsView,
    MemberPushSubscribeView,
    NotificationViewSet,
    TemplateViewSet,
    WhatsAppWebhookView,
)

router = DefaultRouter()
router.register("notifications/templates", TemplateViewSet, basename="notification-template")
router.register("notifications/log", NotificationViewSet, basename="notification-log")
router.register("notifications/broadcasts", BroadcastViewSet, basename="notification-broadcast")
router.register("notifications/announcements", AnnouncementViewSet, basename="announcement")

urlpatterns = [
    path(
        "notifications/broadcasts/estimate",
        BroadcastEstimateView.as_view(),
        name="notification-broadcast-estimate",
    ),
    path(
        "notifications/whatsapp/webhook",
        WhatsAppWebhookView.as_view(),
        name="notification-whatsapp-webhook",
    ),
    path(
        "m/pass/<str:token>/announcements",
        MemberAnnouncementsView.as_view(),
        name="member-announcements",
    ),
    path(
        "m/pass/<str:token>/push-subscribe",
        MemberPushSubscribeView.as_view(),
        name="member-push-subscribe",
    ),
    *router.urls,
]
