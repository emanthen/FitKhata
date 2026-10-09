from django.urls import path
from rest_framework.routers import DefaultRouter

from billing.views import (
    CashShiftCloseView,
    CashShiftOpenView,
    CollectPaymentView,
    CreditNoteViewSet,
    FonepayQrView,
    FonepayStatusView,
    InvoicePdfView,
    InvoiceReceiptTextView,
    MemberInvoiceListView,
    MemberInvoicePdfView,
    MemberRenewalAddOnsView,
    MemberRenewalCallbackView,
    MemberRenewalInitiateView,
    MemberRenewalPlansView,
    ReceiptLinkPdfView,
    SendReceiptSmsView,
    SettlementReportView,
)

router = DefaultRouter()
router.register("credit-notes", CreditNoteViewSet, basename="credit-note")

urlpatterns = [
    path("billing/payments", CollectPaymentView.as_view(), name="billing-collect-payment"),
    path("billing/payments/fonepay/qr", FonepayQrView.as_view(), name="billing-fonepay-qr"),
    path(
        "billing/payments/fonepay/<int:payment_id>/status",
        FonepayStatusView.as_view(),
        name="billing-fonepay-status",
    ),
    path("billing/shifts", CashShiftOpenView.as_view(), name="billing-shift-open"),
    path(
        "billing/shifts/<int:shift_id>/close",
        CashShiftCloseView.as_view(),
        name="billing-shift-close",
    ),
    path("billing/settlement-report", SettlementReportView.as_view(), name="billing-settlement"),
    path(
        "billing/invoices/<int:invoice_id>/pdf",
        InvoicePdfView.as_view(),
        name="billing-invoice-pdf",
    ),
    path(
        "billing/invoices/<int:invoice_id>/receipt-text",
        InvoiceReceiptTextView.as_view(),
        name="billing-invoice-receipt-text",
    ),
    path(
        "billing/invoices/<int:invoice_id>/send-receipt-sms",
        SendReceiptSmsView.as_view(),
        name="billing-send-receipt-sms",
    ),
    path("billing/receipts/<str:token>", ReceiptLinkPdfView.as_view(), name="billing-receipt-link"),
    path(
        "m/pass/<str:token>/plans",
        MemberRenewalPlansView.as_view(),
        name="billing-renewal-plans",
    ),
    path(
        "m/pass/<str:token>/addons",
        MemberRenewalAddOnsView.as_view(),
        name="billing-renewal-addons",
    ),
    path(
        "m/pass/<str:token>/renew",
        MemberRenewalInitiateView.as_view(),
        name="billing-renewal-initiate",
    ),
    path(
        "m/pass/<str:token>/invoices",
        MemberInvoiceListView.as_view(),
        name="member-invoice-list",
    ),
    path(
        "m/pass/<str:token>/invoices/<int:invoice_id>/pdf",
        MemberInvoicePdfView.as_view(),
        name="member-invoice-pdf",
    ),
    path(
        "billing/renewals/callback",
        MemberRenewalCallbackView.as_view(),
        name="billing-renewal-callback",
    ),
    *router.urls,
]
