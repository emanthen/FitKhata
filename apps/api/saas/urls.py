from django.urls import path

from saas.views import (
    AnnouncementBroadcastView,
    DeleteAccountView,
    ExportDataView,
    FeatureFlagListView,
    ImpersonateView,
    MarkInvoicePaidBankView,
    MetricsView,
    SaasInvoiceCallbackView,
    SaasInvoiceListView,
    SaasInvoicePayView,
    SmsWalletTopupCallbackView,
    SmsWalletTopupView,
    SubscriptionView,
    SupportTicketListView,
    SupportTicketMessageView,
    TenantListView,
    TicketInboxView,
)

urlpatterns = [
    # --- tenant-facing ---
    path("saas/subscription", SubscriptionView.as_view(), name="saas-subscription"),
    path("saas/invoices", SaasInvoiceListView.as_view(), name="saas-invoices"),
    path(
        "saas/invoices/<int:invoice_id>/pay", SaasInvoicePayView.as_view(), name="saas-invoice-pay"
    ),
    path(
        "saas/invoices/<int:invoice_id>/callback",
        SaasInvoiceCallbackView.as_view(),
        name="saas-invoice-callback",
    ),
    path("saas/sms-wallet/topup", SmsWalletTopupView.as_view(), name="saas-sms-topup"),
    path(
        "saas/sms-wallet/topup/<int:invoice_id>/callback",
        SmsWalletTopupCallbackView.as_view(),
        name="saas-sms-topup-callback",
    ),
    path("saas/support-tickets", SupportTicketListView.as_view(), name="saas-tickets"),
    path(
        "saas/support-tickets/<int:ticket_id>/messages",
        SupportTicketMessageView.as_view(),
        name="saas-ticket-messages",
    ),
    path("saas/export-data", ExportDataView.as_view(), name="saas-export-data"),
    path("saas/delete-account", DeleteAccountView.as_view(), name="saas-delete-account"),
    # --- platform (FitKhata staff only) ---
    path("platform/tenants", TenantListView.as_view(), name="platform-tenants"),
    path("platform/metrics", MetricsView.as_view(), name="platform-metrics"),
    path("platform/impersonate", ImpersonateView.as_view(), name="platform-impersonate"),
    path("platform/feature-flags", FeatureFlagListView.as_view(), name="platform-feature-flags"),
    path(
        "platform/announcements",
        AnnouncementBroadcastView.as_view(),
        name="platform-announcements",
    ),
    path("platform/tickets", TicketInboxView.as_view(), name="platform-tickets"),
    path(
        "platform/saas-invoices/<int:invoice_id>/mark-paid-bank",
        MarkInvoicePaidBankView.as_view(),
        name="platform-mark-paid-bank",
    ),
]
