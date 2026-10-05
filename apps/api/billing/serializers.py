from __future__ import annotations

from rest_framework import serializers

from billing.models import Invoice, InvoiceLine


class InvoiceLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceLine
        fields = ["id", "description", "quantity", "unit_price_npr", "line_total_npr"]


class InvoiceSerializer(serializers.ModelSerializer):
    lines = InvoiceLineSerializer(many=True, read_only=True)

    class Meta:
        model = Invoice
        fields = [
            "id",
            "number",
            "fiscal_year",
            "status",
            "member",
            "subtotal_npr",
            "discount_npr",
            "total_npr",
            "lines",
            "created_at",
        ]
        read_only_fields = fields
