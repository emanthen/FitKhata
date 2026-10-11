from __future__ import annotations

import json

from rest_framework import serializers

from billing.domain.shift import variance
from billing.models import (
    CashShift,
    CreditNote,
    GatewayCredential,
    Invoice,
    InvoiceLine,
    Payment,
    Product,
    Sale,
    SaleLine,
)
from billing.services import shift_expected_cash_npr
from core.crypto import encrypt_bytes


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
            "taxable_npr",
            "vat_npr",
            "total_npr",
            "bill_date",
            "bill_date_bs",
            "buyer_name",
            "buyer_pan",
            "void_reason",
            "lines",
            "created_at",
        ]
        read_only_fields = fields


class GatewayCredentialSerializer(serializers.ModelSerializer):
    """`secret`/`username`/`password`/`hmac_key` are write-only inputs —
    never read back out once stored (core.crypto Fernet-encrypted, the
    same stance Member.qr_secret takes). `is_configured` is what the
    settings UI shows instead of the real secret.
    """

    secret = serializers.CharField(write_only=True, required=False, allow_blank=True)
    username = serializers.CharField(write_only=True, required=False, allow_blank=True)
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    hmac_key = serializers.CharField(write_only=True, required=False, allow_blank=True)
    is_configured = serializers.SerializerMethodField()

    class Meta:
        model = GatewayCredential
        fields = [
            "id",
            "provider",
            "environment",
            "merchant_code",
            "secret",
            "username",
            "password",
            "hmac_key",
            "is_configured",
            "is_active",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def get_is_configured(self, obj: GatewayCredential) -> bool:
        return bool(bytes(obj.secret_encrypted))

    def _pack_secret(self, validated_data: dict) -> bytes | None:
        """eSewa/Khalti: secret_encrypted is just the plain secret string.
        Fonepay: secret_encrypted is JSON {"password", "hmac_key"} — see
        billing/gateways/fonepay.py's module docstring for why.
        """
        provider = validated_data.get("provider")
        if provider == GatewayCredential.Provider.FONEPAY:
            password = validated_data.pop("password", None)
            hmac_key = validated_data.pop("hmac_key", None)
            username = validated_data.pop("username", None)
            if username is not None:
                validated_data["extra"] = {"username": username}
            if password is None and hmac_key is None:
                return None
            return encrypt_bytes(
                json.dumps({"password": password or "", "hmac_key": hmac_key or ""}).encode(
                    "utf-8"
                )
            )
        secret = validated_data.pop("secret", None)
        validated_data.pop("username", None)
        validated_data.pop("password", None)
        validated_data.pop("hmac_key", None)
        if not secret:
            return None
        return encrypt_bytes(secret.encode("utf-8"))

    def create(self, validated_data: dict) -> GatewayCredential:
        secret_encrypted = self._pack_secret(validated_data)
        validated_data["secret_encrypted"] = secret_encrypted or b""
        return super().create(validated_data)

    def update(self, instance: GatewayCredential, validated_data: dict) -> GatewayCredential:
        secret_encrypted = self._pack_secret(validated_data)
        if secret_encrypted is not None:
            instance.secret_encrypted = secret_encrypted
        return super().update(instance, validated_data)


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = [
            "id",
            "member",
            "invoice",
            "shift",
            "mode",
            "channel",
            "transaction_uuid",
            "gateway_ref",
            "amount_npr",
            "status",
            "receipt_no",
            "collected_by",
            "created_at",
        ]
        read_only_fields = fields


class CollectPaymentSerializer(serializers.Serializer):
    invoice_id = serializers.IntegerField()
    mode = serializers.ChoiceField(
        choices=[
            Payment.Mode.CASH,
            Payment.Mode.MANUAL_ESEWA,
            Payment.Mode.BANK,
            Payment.Mode.CHEQUE,
        ]
    )
    amount_npr = serializers.DecimalField(max_digits=12, decimal_places=2)
    shift_id = serializers.IntegerField(required=False, allow_null=True)


class CashShiftSerializer(serializers.ModelSerializer):
    expected_cash_npr = serializers.SerializerMethodField()
    variance_npr = serializers.SerializerMethodField()

    class Meta:
        model = CashShift
        fields = [
            "id",
            "staff",
            "opened_at",
            "closed_at",
            "opening_float_npr",
            "counted_cash_npr",
            "denominations",
            "expected_cash_npr",
            "variance_npr",
        ]
        read_only_fields = fields

    def get_expected_cash_npr(self, obj: CashShift) -> str:
        return str(shift_expected_cash_npr(obj))

    def get_variance_npr(self, obj: CashShift) -> str | None:
        if obj.counted_cash_npr is None:
            return None
        return str(variance(shift_expected_cash_npr(obj), obj.counted_cash_npr))


class CreditNoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = CreditNote
        fields = [
            "id",
            "invoice",
            "amount_npr",
            "reason",
            "approved_by",
            "approved_at",
            "created_at",
        ]
        read_only_fields = ["id", "approved_by", "approved_at", "created_at"]


class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ["id", "sku", "name", "price_npr", "stock_qty", "is_active"]
        read_only_fields = ["id"]


class SaleLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = SaleLine
        fields = ["id", "product", "quantity", "unit_price_npr", "line_total_npr"]
        read_only_fields = fields


class SaleSerializer(serializers.ModelSerializer):
    lines = SaleLineSerializer(many=True, read_only=True)

    class Meta:
        model = Sale
        fields = ["id", "invoice", "created_by", "created_at", "lines"]
        read_only_fields = fields


class SaleLineInputSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1)


class RingUpSaleSerializer(serializers.Serializer):
    member_id = serializers.IntegerField()
    lines = SaleLineInputSerializer(many=True)

    def validate_lines(self, value: list[dict]) -> list[dict]:
        if not value:
            raise serializers.ValidationError("At least one line is required.")
        return value
