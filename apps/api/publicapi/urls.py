"""Owner-facing integration management (create/revoke API keys, manage
webhook subscriptions) -- JWT authenticated, mounted under api/v1/ with
everything else. See public_urls.py for FR-12.3's actual public read API,
mounted separately at api/public/v1/.
"""

from django.urls import path

from publicapi.views import (
    ApiKeyListCreateView,
    ApiKeyRevokeView,
    WebhookDeliveryListView,
    WebhookSubscriptionListCreateView,
)

urlpatterns = [
    path("integrations/api-keys", ApiKeyListCreateView.as_view(), name="api-keys"),
    path(
        "integrations/api-keys/<uuid:pk>/revoke",
        ApiKeyRevokeView.as_view(),
        name="api-key-revoke",
    ),
    path(
        "integrations/webhooks",
        WebhookSubscriptionListCreateView.as_view(),
        name="webhook-subscriptions",
    ),
    path(
        "integrations/webhooks/<uuid:pk>/deliveries",
        WebhookDeliveryListView.as_view(),
        name="webhook-deliveries",
    ),
]
