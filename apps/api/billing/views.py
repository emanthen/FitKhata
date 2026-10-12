from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from django.conf import settings
from django.core import signing
from django.db.models import Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsFrontDeskOrAbove, IsOwner
from accounts.sms import get_sms_provider
from attendance.views import MEMBER_PASS_MAX_AGE, MEMBER_PASS_SALT
from billing.domain.shift import variance
from billing.gateways import get_gateway
from billing.gateways.base import GatewayNotConfigured, GatewayVerificationFailed
from billing.models import CashShift, CreditNote, GatewayCredential, Invoice, Payment, Product
from billing.receipts import render_invoice_pdf, render_receipt_text
from billing.serializers import (
    CashShiftSerializer,
    CollectPaymentSerializer,
    CreditNoteSerializer,
    GatewayCredentialSerializer,
    InvoiceSerializer,
    PaymentSerializer,
    ProductSerializer,
    RingUpSaleSerializer,
    SaleSerializer,
)
from billing.services import (
    InsufficientStock,
    SaleLineInput,
    collect_payment,
    record_pos_sale,
    shift_expected_cash_npr,
)
from core.context import system_context
from core.services import audit
from core.viewsets import TenantQuerysetMixin, TenantViewSet
from members.models import AddOn, Member, Plan, PromoCode
from members.services import PromoNotApplicable, initiate_renewal_payment

RECEIPT_LINK_SALT = "billing.receipt-link"
RECEIPT_LINK_MAX_AGE = 30 * 24 * 60 * 60  # 30 days — plenty for "check your SMS"

VARIANCE_NOTIFY_THRESHOLD_NPR = Decimal("100.00")


class InvoiceViewSet(TenantQuerysetMixin, viewsets.ReadOnlyModelViewSet):
    """Read-only (plus the one controlled `void` action below) — draft
    invoices are only ever created by billing.services.create_draft_invoice
    and only ever transition status via collect_payment()/void(), never
    through a raw update/delete on this API (rule 7). TenantQuerysetMixin,
    not TenantViewSet: the latter pulls in full ModelViewSet (create/
    update/destroy), which would defeat the point.
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

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[permissions.IsAuthenticated, IsOwner],
    )
    def void(self, request, pk=None):
        """Rule 8: never delete a numbered invoice, void it with a reason
        instead — owner-gated, same sensitivity as a credit note.
        """
        invoice = self.get_object()
        if invoice.status == Invoice.Status.VOID:
            return Response({"detail": "Already void."}, status=400)
        reason = request.data.get("reason", "").strip()
        if not reason:
            return Response({"detail": "A reason is required to void an invoice."}, status=400)

        before_status = invoice.status
        invoice.status = Invoice.Status.VOID
        invoice.void_reason = reason
        invoice.save(update_fields=["status", "void_reason"])
        audit(
            invoice,
            "void",
            before={"status": before_status},
            after={"status": Invoice.Status.VOID, "void_reason": reason},
            actor=request.user,
        )
        return Response(InvoiceSerializer(invoice).data)


class GatewayCredentialViewSet(TenantViewSet):
    """IsOwner-only — these are merchant credentials, rule 10's "encrypted
    per-gym payment keys".
    """

    serializer_class = GatewayCredentialSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwner]
    queryset = GatewayCredential.objects.all()

    @action(detail=True, methods=["post"], url_path="test-connection")
    def test_connection(self, request, pk=None):
        """A best-effort reachability/shape check, not a guarantee the
        secret is correct — eSewa has no "validate credentials" endpoint
        short of an actual payment attempt; Khalti's initiate call does
        reject a wrong secret key outright, so for Khalti this is a real
        credential check. Either way: a failure here is trustworthy (the
        gateway/network is reachable and something is wrong), a success
        for eSewa specifically just means "the request was well-formed".
        """
        credential = self.get_object()

        class _StubMember:
            member_code = "TEST-0000"

        class _StubPayment:
            gym = credential.gym
            amount_npr = Decimal("10.00")
            transaction_uuid = uuid.uuid4()
            member = _StubMember()

        try:
            gateway = get_gateway(credential.provider)
            gateway.initiate(_StubPayment(), return_url="https://example.invalid/test")
        except Exception as exc:  # noqa: BLE001 — surfacing *any* failure reason to the UI is the point
            return Response({"ok": False, "detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"ok": True})


class CollectPaymentView(APIView):
    """FR-4.9's collect-payment drawer: cash / manual eSewa / bank / cheque
    against an existing (draft) invoice — Fonepay desk QR has its own
    initiate/poll views below since it isn't a one-shot synchronous
    collection. Supports partial payments: the invoice only transitions to
    issued once collect_payment() sees the cumulative total covered.
    """

    permission_classes = [permissions.IsAuthenticated, IsFrontDeskOrAbove]

    def post(self, request):
        if request.gym is None:
            return Response({"detail": "X-Gym-Id header is required."}, status=400)
        serializer = CollectPaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        invoice = get_object_or_404(Invoice, pk=data["invoice_id"], gym=request.gym)
        shift = None
        if data.get("shift_id"):
            shift = get_object_or_404(CashShift, pk=data["shift_id"], gym=request.gym)

        payment = Payment.objects.create(
            org=request.gym.org,
            gym=request.gym,
            member=invoice.member,
            invoice=invoice,
            shift=shift,
            mode=data["mode"],
            channel=Payment.Channel.DESK,
            transaction_uuid=uuid.uuid4(),
            amount_npr=data["amount_npr"],
            status=Payment.Status.PENDING,
            collected_by=request.user,
        )
        result = collect_payment(payment, actor=request.user)
        return Response(PaymentSerializer(result).data, status=status.HTTP_201_CREATED)


class FonepayQrView(APIView):
    """Generates a desk Fonepay QR for an invoice's outstanding amount.
    The desk then polls FonepayStatusView (or listens on the websocket URL
    handed back here) until it's paid.
    """

    permission_classes = [permissions.IsAuthenticated, IsFrontDeskOrAbove]

    def post(self, request):
        if request.gym is None:
            return Response({"detail": "X-Gym-Id header is required."}, status=400)
        invoice_id = request.data.get("invoice_id")
        amount_npr = request.data.get("amount_npr")
        invoice = get_object_or_404(Invoice, pk=invoice_id, gym=request.gym)

        payment = Payment.objects.create(
            org=request.gym.org,
            gym=request.gym,
            member=invoice.member,
            invoice=invoice,
            mode=Payment.Mode.FONEPAY,
            channel=Payment.Channel.DESK,
            transaction_uuid=uuid.uuid4(),
            amount_npr=Decimal(str(amount_npr)),
            status=Payment.Status.PENDING,
            collected_by=request.user,
        )
        try:
            gateway = get_gateway(GatewayCredential.Provider.FONEPAY)
            instructions = gateway.initiate(payment, return_url="")
        except (GatewayNotConfigured, GatewayVerificationFailed) as exc:
            return Response({"detail": str(exc)}, status=400)

        return Response(
            {
                "payment_id": payment.pk,
                "qr_message": instructions.url,
                "websocket_url": instructions.fields.get("websocket_url", ""),
            },
            status=status.HTTP_201_CREATED,
        )


class FonepayStatusView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsFrontDeskOrAbove]

    def post(self, request, payment_id: int):
        payment = get_object_or_404(
            Payment, pk=payment_id, gym=request.gym, mode=Payment.Mode.FONEPAY
        )
        if payment.status == Payment.Status.COMPLETED:
            return Response(PaymentSerializer(payment).data)

        gateway = get_gateway(GatewayCredential.Provider.FONEPAY)
        result = gateway.verify({"prn": str(payment.transaction_uuid), "gym": request.gym})
        if result.completed:
            payment = collect_payment(
                payment,
                gateway_ref=result.gateway_ref,
                raw_response=result.raw_response,
                actor=request.user,
            )
        return Response(PaymentSerializer(payment).data)


class CashShiftOpenView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsFrontDeskOrAbove]

    def post(self, request):
        if request.gym is None:
            return Response({"detail": "X-Gym-Id header is required."}, status=400)
        opening_float = Decimal(str(request.data.get("opening_float_npr", "0")))
        shift = CashShift.objects.create(
            org=request.gym.org,
            gym=request.gym,
            staff=request.user,
            opening_float_npr=opening_float,
        )
        audit(shift, "create", after={"opening_float_npr": str(opening_float)}, actor=request.user)
        return Response(CashShiftSerializer(shift).data, status=status.HTTP_201_CREATED)


class CashShiftCloseView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsFrontDeskOrAbove]

    def post(self, request, shift_id: int):
        shift = get_object_or_404(CashShift, pk=shift_id, gym=request.gym)
        if shift.closed_at is not None:
            return Response({"detail": "Shift already closed."}, status=400)

        denominations = request.data.get("denominations", {})
        counted = Decimal(str(request.data.get("counted_cash_npr", "0")))
        expected = shift_expected_cash_npr(shift)
        shift_variance = variance(expected, counted)

        shift.closed_at = timezone.now()
        shift.counted_cash_npr = counted
        shift.denominations = denominations
        shift.save(update_fields=["closed_at", "counted_cash_npr", "denominations"])
        audit(
            shift,
            "update",
            after={
                "closed": True,
                "expected_cash_npr": str(expected),
                "counted_cash_npr": str(counted),
                "variance_npr": str(shift_variance),
            },
            actor=request.user,
        )

        if abs(shift_variance) > VARIANCE_NOTIFY_THRESHOLD_NPR:
            _notify_owners_of_variance(request.gym, shift, shift_variance)

        payload = CashShiftSerializer(shift).data
        return Response(payload)


def _notify_owners_of_variance(gym: Any, shift: CashShift, shift_variance: Decimal) -> None:
    from django.db.models import Q

    from accounts.models import StaffRole

    # Same gym-or-org-wide shape as attendance.consumers._has_role_on_gym —
    # an org-wide owner (gym=None) oversees every branch, a gym-scoped one
    # only this gym.
    owners = StaffRole.objects.filter(
        org=gym.org, role=StaffRole.Role.OWNER, is_active=True
    ).filter(Q(gym=gym) | Q(gym__isnull=True)).select_related("user")

    message = (
        f"FitKhata: cash shift variance of NPR {shift_variance} at {gym.name} "
        f"(shift #{shift.pk}, closed by {shift.staff})."
    )
    provider = get_sms_provider()
    for staff_role in owners:
        if staff_role.user.phone:
            provider.send(staff_role.user.phone, message)


class CreditNoteViewSet(
    TenantQuerysetMixin,
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Create + read + the controlled `approve` action only — no raw
    update/destroy. Same rule-7 reasoning as Invoice: once a credit note
    exists (and especially once an owner has approved it), front-desk must
    not be able to silently edit its amount/reason out from under that
    approval, or delete the record outright.
    """

    serializer_class = CreditNoteSerializer
    permission_classes = [permissions.IsAuthenticated, IsFrontDeskOrAbove]
    queryset = CreditNote.objects.all()

    def perform_create(self, serializer):
        if self.request.gym is None:
            raise PermissionDenied("X-Gym-Id header is required.")
        serializer.save(gym=self.request.gym, org=self.request.gym.org)

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[permissions.IsAuthenticated, IsOwner],
    )
    def approve(self, request, pk=None):
        """FR-4.8: a credit note needs an owner's sign-off before it takes
        effect on the invoice.
        """
        credit_note = self.get_object()
        if credit_note.approved_by_id is not None:
            return Response({"detail": "Already approved."}, status=400)

        credit_note.approved_by = request.user
        credit_note.approved_at = timezone.now()
        credit_note.save(update_fields=["approved_by", "approved_at"])
        audit(credit_note, "update", after={"approved": True}, actor=request.user)
        return Response(CreditNoteSerializer(credit_note).data)


class ProductViewSet(TenantViewSet):
    """FR-12.7 POS: retail stock, manager+ CRUD."""

    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticated, IsFrontDeskOrAbove]
    queryset = Product.objects.all()


class RingUpSaleView(APIView):
    """FR-12.7: front-desk rings up retail stock against a member, through
    billing.services.record_pos_sale (which itself reuses
    create_draft_invoice -- see that function's own docstring).
    """

    permission_classes = [permissions.IsAuthenticated, IsFrontDeskOrAbove]

    def post(self, request):
        if request.gym is None:
            return Response({"detail": "X-Gym-Id header is required."}, status=400)
        serializer = RingUpSaleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        member = get_object_or_404(Member, pk=data["member_id"], gym=request.gym)
        lines = [
            SaleLineInput(product_id=line["product_id"], quantity=line["quantity"])
            for line in data["lines"]
        ]

        try:
            sale = record_pos_sale(request.gym, member, lines, actor=request.user)
        except InsufficientStock as exc:
            return Response({"detail": str(exc)}, status=400)

        return Response(SaleSerializer(sale).data, status=status.HTTP_201_CREATED)


class SettlementReportView(APIView):
    """FR-4.11: payments collected on a given day, summed by mode."""

    permission_classes = [permissions.IsAuthenticated, IsFrontDeskOrAbove]

    def get(self, request):
        if request.gym is None:
            return Response({"detail": "X-Gym-Id header is required."}, status=400)
        date_str = request.query_params.get("date")
        report_date = date.fromisoformat(date_str) if date_str else date.today()

        payments = Payment.objects.filter(
            gym=request.gym,
            status=Payment.Status.COMPLETED,
            updated_at__date=report_date,
        )
        by_mode = {
            row["mode"]: str(row["total"])
            for row in payments.values("mode").annotate(total=Sum("amount_npr"))
        }
        total = payments.aggregate(total=Sum("amount_npr"))["total"] or Decimal("0.00")
        return Response(
            {"date": report_date.isoformat(), "by_mode": by_mode, "total_npr": str(total)}
        )


# --- Member-facing online renewal (token-authenticated, see MemberPassView) --


class MemberRenewalPlansView(APIView):
    """What the Member PWA's renewal screen needs before it can call
    MemberRenewalInitiateView: the member's own gym's active plans to
    choose from. Same token auth as the rest of this family.
    """

    permission_classes = [permissions.AllowAny]

    def get(self, request, token: str):
        try:
            token_data = signing.loads(token, salt=MEMBER_PASS_SALT, max_age=MEMBER_PASS_MAX_AGE)
        except signing.SignatureExpired:
            return Response({"detail": "This pass link has expired."}, status=400)
        except signing.BadSignature:
            return Response({"detail": "Invalid pass link."}, status=400)

        with system_context():
            member = get_object_or_404(Member, pk=token_data["member_id"])
            plans = Plan.objects.filter(gym=member.gym, is_active=True).order_by("price_npr")
            return Response(
                [
                    {
                        "id": plan.pk,
                        "name": plan.name,
                        "duration_days": plan.duration_days,
                        "price_npr": str(plan.price_npr),
                    }
                    for plan in plans
                ]
            )


class MemberRenewalAddOnsView(APIView):
    """The renewal screen's optional add-ons list (FR-8.3: "choose plan/
    add-ons/promo"), same token auth and gym-scoping as MemberRenewalPlansView.
    """

    permission_classes = [permissions.AllowAny]

    def get(self, request, token: str):
        try:
            token_data = signing.loads(token, salt=MEMBER_PASS_SALT, max_age=MEMBER_PASS_MAX_AGE)
        except signing.SignatureExpired:
            return Response({"detail": "This pass link has expired."}, status=400)
        except signing.BadSignature:
            return Response({"detail": "Invalid pass link."}, status=400)

        with system_context():
            member = get_object_or_404(Member, pk=token_data["member_id"])
            addons = AddOn.objects.filter(gym=member.gym).order_by("name")
            return Response(
                [
                    {
                        "id": addon.pk,
                        "name": addon.name,
                        "price_npr": str(addon.price_npr),
                        "kind": addon.kind,
                    }
                    for addon in addons
                ]
            )


class MemberRenewalInitiateView(APIView):
    """Member-initiated eSewa/Khalti/Fonepay renewal from the Member PWA.
    Reuses the exact same signed pass-link token as MemberPassView/
    attendance.views — that token is already this app's proof of a
    member's identity for the PWA, no separate login system needed for
    this. Fonepay's initiate() hands back a QR payload instead of a
    redirect (see gateways/fonepay.py) — the PWA renders that itself and
    polls MemberRenewalCallbackView rather than navigating anywhere.
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request, token: str):
        try:
            token_data = signing.loads(token, salt=MEMBER_PASS_SALT, max_age=MEMBER_PASS_MAX_AGE)
        except signing.SignatureExpired:
            return Response({"detail": "This pass link has expired."}, status=400)
        except signing.BadSignature:
            return Response({"detail": "Invalid pass link."}, status=400)

        plan_id = request.data.get("plan_id")
        provider = request.data.get("provider")
        return_url = request.data.get("return_url", "")
        promo_code = (request.data.get("promo_code") or "").strip()
        addon_ids = request.data.get("addon_ids") or []
        if provider not in (
            GatewayCredential.Provider.ESEWA,
            GatewayCredential.Provider.KHALTI,
            GatewayCredential.Provider.FONEPAY,
        ):
            return Response({"detail": "Unsupported provider for online renewal."}, status=400)

        with system_context():
            member = get_object_or_404(Member, pk=token_data["member_id"])
            plan = get_object_or_404(Plan, pk=plan_id, gym=member.gym)

            promo = None
            if promo_code:
                promo = PromoCode.objects.filter(
                    gym=member.gym, code__iexact=promo_code
                ).first()
                if promo is None:
                    return Response({"detail": "Invalid promo code."}, status=400)
            addons = list(AddOn.objects.filter(gym=member.gym, pk__in=addon_ids))

            try:
                payment = initiate_renewal_payment(
                    member, plan, provider, promo=promo, addons=addons
                )
            except PromoNotApplicable as exc:
                return Response({"detail": str(exc)}, status=400)

            try:
                gateway = get_gateway(provider)
                instructions = gateway.initiate(payment, return_url=return_url)
            except GatewayNotConfigured as exc:
                return Response({"detail": str(exc)}, status=400)

            if instructions.reference:
                payment.gateway_ref = instructions.reference
                payment.save(update_fields=["gateway_ref"])

            return Response(
                {
                    "payment_id": payment.pk,
                    "redirect": {
                        "url": instructions.url,
                        "method": instructions.method,
                        "fields": instructions.fields,
                    },
                }
            )


class MemberRenewalCallbackView(APIView):
    """Where the Member PWA asks "did it work?" — no token needed here, the
    payment_id + gateway's own signature/lookup verification is the
    authority (rule 6). eSewa/Khalti call this once, right after the
    browser redirects back; Fonepay has no redirect at all, so the PWA
    calls this repeatedly (polling) while the member is scanning the QR.
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        provider = request.data.get("provider")
        payment_id = request.data.get("payment_id")

        with system_context():
            payment = get_object_or_404(Payment, pk=payment_id)
            if payment.status == Payment.Status.COMPLETED:
                return Response({"status": "completed"})

            callback_data: dict[str, Any] = {"gym": payment.gym, "payment": payment}
            if provider == GatewayCredential.Provider.ESEWA:
                callback_data["data"] = request.data.get("data", "")
            elif provider == GatewayCredential.Provider.KHALTI:
                callback_data["pidx"] = payment.gateway_ref
                callback_data["expected_amount_paisa"] = int(payment.amount_npr * 100)
            elif provider == GatewayCredential.Provider.FONEPAY:
                callback_data["prn"] = str(payment.transaction_uuid)
            else:
                return Response({"detail": "Unsupported provider."}, status=400)

            try:
                gateway = get_gateway(provider)
                result = gateway.verify(callback_data)
            except GatewayVerificationFailed as exc:
                return Response({"detail": str(exc)}, status=400)

            if not result.completed:
                return Response({"status": "pending"})

            collect_payment(
                payment, gateway_ref=result.gateway_ref, raw_response=result.raw_response
            )

        return Response({"status": "completed"})


# --- Receipts: PDF, plain-text (browser-print fallback), SMS link ----------


class InvoicePdfView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsFrontDeskOrAbove]

    def get(self, request, invoice_id: int):
        invoice = get_object_or_404(Invoice, pk=invoice_id, gym=request.gym)
        pdf_bytes = render_invoice_pdf(invoice)
        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename="{invoice.number}.pdf"'
        return response


class InvoiceReceiptTextView(APIView):
    """Plain-text 80mm receipt — what the admin UI's window.print()
    fallback renders today, and what apps/bridge will eventually wrap in
    real ESC/POS byte commands (Phase 12).
    """

    permission_classes = [permissions.IsAuthenticated, IsFrontDeskOrAbove]

    def get(self, request, invoice_id: int):
        invoice = get_object_or_404(Invoice, pk=invoice_id, gym=request.gym)
        return Response({"text": render_receipt_text(invoice)})


class SendReceiptSmsView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsFrontDeskOrAbove]

    def post(self, request, invoice_id: int):
        invoice = get_object_or_404(Invoice, pk=invoice_id, gym=request.gym)
        if not invoice.member.phone:
            return Response({"detail": "This member has no phone number on file."}, status=400)

        token = signing.dumps({"invoice_id": invoice.pk}, salt=RECEIPT_LINK_SALT)
        link = f"{settings.API_PUBLIC_URL}/api/v1/billing/receipts/{token}"
        message = f"FitKhata receipt for invoice {invoice.number}: {link}"
        get_sms_provider().send(invoice.member.phone, message)
        return Response({"sent": True})


class MemberInvoiceListView(APIView):
    """FR-8.6: the Member PWA's own invoice/receipt list. Same pass-token
    auth as the rest of the m/pass/<token>/... family.
    """

    permission_classes = [permissions.AllowAny]

    def get(self, request, token: str):
        try:
            data = signing.loads(token, salt=MEMBER_PASS_SALT, max_age=MEMBER_PASS_MAX_AGE)
        except signing.SignatureExpired:
            return Response({"detail": "This pass link has expired."}, status=400)
        except signing.BadSignature:
            return Response({"detail": "Invalid pass link."}, status=400)

        with system_context():
            member = get_object_or_404(Member, pk=data["member_id"])
            invoices = Invoice.objects.filter(member=member).order_by("-bill_date")
            return Response(InvoiceSerializer(invoices, many=True).data)


class MemberInvoicePdfView(APIView):
    """A dedicated member-scoped sibling of InvoicePdfView, not a reuse of
    it or of ReceiptLinkPdfView: InvoicePdfView is staff-only, and
    ReceiptLinkPdfView's token is a one-shot per-invoice SMS link, not this
    member's long-lived pass token. Checking invoice.member_id here keeps
    the pass token from quietly becoming an all-invoices key.
    """

    permission_classes = [permissions.AllowAny]

    def get(self, request, token: str, invoice_id: int):
        try:
            data = signing.loads(token, salt=MEMBER_PASS_SALT, max_age=MEMBER_PASS_MAX_AGE)
        except signing.SignatureExpired:
            return Response({"detail": "This pass link has expired."}, status=400)
        except signing.BadSignature:
            return Response({"detail": "Invalid pass link."}, status=400)

        with system_context():
            member = get_object_or_404(Member, pk=data["member_id"])
            invoice = get_object_or_404(Invoice, pk=invoice_id, member=member)
            pdf_bytes = render_invoice_pdf(invoice)
            response = HttpResponse(pdf_bytes, content_type="application/pdf")
            response["Content-Disposition"] = f'inline; filename="{invoice.number}.pdf"'
            return response


class ReceiptLinkPdfView(APIView):
    """Unauthenticated — the signed token itself is the proof, same shape
    as attendance.views.MemberPassView. An SMS link can't carry an auth
    header, so this is how a receipt actually gets opened from one.
    """

    permission_classes = [permissions.AllowAny]

    def get(self, request, token: str):
        try:
            data = signing.loads(token, salt=RECEIPT_LINK_SALT, max_age=RECEIPT_LINK_MAX_AGE)
        except signing.SignatureExpired:
            return Response({"detail": "This receipt link has expired."}, status=400)
        except signing.BadSignature:
            return Response({"detail": "Invalid receipt link."}, status=400)

        with system_context():
            invoice = get_object_or_404(Invoice, pk=data["invoice_id"])
            pdf_bytes = render_invoice_pdf(invoice)
            response = HttpResponse(pdf_bytes, content_type="application/pdf")
            response["Content-Disposition"] = f'inline; filename="{invoice.number}.pdf"'
            return response
