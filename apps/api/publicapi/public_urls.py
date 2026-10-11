"""FR-12.3: the actual public read API, API-key authenticated, mounted at
api/public/v1/ by config/urls.py.
"""

from django.urls import path

from publicapi.views import PublicInvoiceListView, PublicMemberListView, PublicMembershipListView

urlpatterns = [
    path("members", PublicMemberListView.as_view(), name="public-members"),
    path("memberships", PublicMembershipListView.as_view(), name="public-memberships"),
    path("invoices", PublicInvoiceListView.as_view(), name="public-invoices"),
]
