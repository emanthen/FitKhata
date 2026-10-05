from __future__ import annotations

from rest_framework import permissions, viewsets

from accounts.permissions import IsFrontDeskOrAbove
from billing.models import Invoice
from billing.serializers import InvoiceSerializer
from core.viewsets import TenantQuerysetMixin


class InvoiceViewSet(TenantQuerysetMixin, viewsets.ReadOnlyModelViewSet):
    """Read-only — draft invoices are only ever created by
    billing.services.create_draft_invoice, never through this API.
    """

    serializer_class = InvoiceSerializer
    permission_classes = [permissions.IsAuthenticated, IsFrontDeskOrAbove]
    queryset = Invoice.objects.all()

    def get_queryset(self):
        qs = super().get_queryset()
        member_id = self.request.query_params.get("member")
        if member_id:
            qs = qs.filter(member_id=member_id)
        return qs
