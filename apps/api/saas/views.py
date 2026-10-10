"""Thin views (rule 9) — two audiences: /saas/... (tenant-facing,
IsAuthenticated + gym-scoped) and /platform/... (FitKhata-staff-only,
IsPlatformStaff, never gym-scoped).
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from django.db.models import Count
from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import StaffRole
from accounts.permissions import IsManagerOrAbove, IsOwner
from billing.gateways.base import GatewayNotConfigured, GatewayVerificationFailed
from billing.models import GatewayCredential
from core.context import system_context
from gyms.models import Organization
from notifications.providers import email as email_provider
from notifications.providers import whatsapp as whatsapp_provider
from saas import gateways, services
from saas.models import FeatureFlag, SaasInvoice, Subscription, SupportTicket
from saas.permissions import IsPlatformStaff

_PROVIDERS = (
    GatewayCredential.Provider.ESEWA,
    GatewayCredential.Provider.KHALTI,
    GatewayCredential.Provider.FONEPAY,
)
_BILLING_STATUSES = (Subscription.Status.ACTIVE, Subscription.Status.GRACE)


def _plan_mrr(sub: Subscription) -> Decimal:
    if sub.plan.per_branch_pricing:
        return sub.plan.monthly_npr * sub.branches
    return sub.plan.monthly_npr


# ============================================================================
# Tenant-facing — /api/v1/saas/...
# ============================================================================


class SubscriptionView(APIView):
    """FR-11.2: what useFeature()/the read-only banner read."""

    permission_classes = [permissions.IsAuthenticated, IsManagerOrAbove]

    def get(self, request):
        if request.gym is None:
            return Response({"detail": "No gym selected."}, status=400)
        with system_context():
            sub = Subscription.objects.select_related("plan").filter(
                org=request.gym.org
            ).first()
            if sub is None:
                return Response({"detail": "No subscription found."}, status=404)
            from members.models import Member

            member_count = Member.objects.filter(org=request.gym.org).count()
            features = {
                key: services.has_feature(request.gym.org, key)
                for key in sub.plan.features
            }
        return Response(
            {
                "plan_code": sub.plan.code,
                "status": sub.status,
                "billing_cycle": sub.billing_cycle,
                "branches": sub.branches,
                "current_period_end": sub.current_period_end,
                "member_limit": sub.plan.member_limit,
                "member_count": member_count,
                "features": features,
            }
        )


class SaasInvoiceListView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsOwner]

    def get(self, request):
        if request.gym is None:
            return Response({"detail": "No gym selected."}, status=400)
        with system_context():
            invoices = list(
                SaasInvoice.objects.filter(org=request.gym.org).order_by("-created_at").values(
                    "id",
                    "number",
                    "kind",
                    "period",
                    "total_npr",
                    "status",
                    "paid_via",
                    "created_at",
                )
            )
        return Response(invoices)


class SaasInvoicePayView(APIView):
    """Initiates a FitKhata-own-merchant gateway payment for one SaaS
    invoice — see saas/gateways.py for why Phase 4's gateway classes are
    reused completely unchanged here.
    """

    permission_classes = [permissions.IsAuthenticated, IsOwner]

    def post(self, request, invoice_id: int):
        provider = request.data.get("provider")
        return_url = request.data.get("return_url", "")
        if provider not in _PROVIDERS:
            return Response({"detail": "Unsupported provider."}, status=400)

        with system_context():
            invoice = get_object_or_404(SaasInvoice, pk=invoice_id, org=request.gym.org)
            if invoice.status == SaasInvoice.Status.PAID:
                return Response({"status": "paid"})
            try:
                instructions = gateways.initiate_platform_payment(
                    invoice.total_npr,
                    invoice.transaction_uuid,
                    provider,
                    reference=invoice.number,
                    return_url=return_url,
                )
            except GatewayNotConfigured as exc:
                return Response({"detail": str(exc)}, status=400)

        return Response(
            {
                "invoice_id": invoice.pk,
                "redirect": {
                    "url": instructions.url,
                    "method": instructions.method,
                    "fields": instructions.fields,
                },
            }
        )


def _verify_and_confirm(invoice: SaasInvoice, provider: str, request) -> Response:
    callback_data: dict[str, Any] = {}
    if provider == GatewayCredential.Provider.ESEWA:
        callback_data["data"] = request.data.get("data", "")
    elif provider == GatewayCredential.Provider.KHALTI:
        callback_data["pidx"] = request.data.get("pidx", "")
        callback_data["expected_amount_paisa"] = int(invoice.total_npr * 100)
    elif provider == GatewayCredential.Provider.FONEPAY:
        callback_data["prn"] = str(invoice.transaction_uuid)
    else:
        return Response({"detail": "Unsupported provider."}, status=400)

    try:
        result = gateways.verify_platform_payment(provider, callback_data)
    except GatewayVerificationFailed as exc:
        return Response({"detail": str(exc)}, status=400)
    if not result.completed:
        return Response({"status": "pending"})

    services.confirm_saas_invoice_payment(
        invoice, paid_via=provider, gateway_ref=result.gateway_ref, raw_response=result.raw_response
    )
    return Response({"status": "paid"})


class SaasInvoiceCallbackView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsOwner]

    def post(self, request, invoice_id: int):
        provider = request.data.get("provider")
        with system_context():
            invoice = get_object_or_404(SaasInvoice, pk=invoice_id, org=request.gym.org)
            if invoice.status == SaasInvoice.Status.PAID:
                return Response({"status": "paid"})
            return _verify_and_confirm(invoice, provider, request)


class SmsWalletTopupView(APIView):
    """FR-11.5 — same gateway round trip as SaaS invoice payment, see
    saas/services.py::initiate_sms_topup_invoice.
    """

    permission_classes = [permissions.IsAuthenticated, IsOwner]

    def post(self, request):
        provider = request.data.get("provider")
        return_url = request.data.get("return_url", "")
        if provider not in _PROVIDERS:
            return Response({"detail": "Unsupported provider."}, status=400)
        try:
            amount = Decimal(str(request.data.get("amount_npr", "")))
        except InvalidOperation:
            return Response({"detail": "Invalid amount_npr."}, status=400)
        if amount <= 0:
            return Response({"detail": "amount_npr must be positive."}, status=400)

        invoice = services.initiate_sms_topup_invoice(request.gym.org, amount)
        try:
            instructions = gateways.initiate_platform_payment(
                invoice.total_npr,
                invoice.transaction_uuid,
                provider,
                reference=invoice.number,
                return_url=return_url,
            )
        except GatewayNotConfigured as exc:
            return Response({"detail": str(exc)}, status=400)

        return Response(
            {
                "invoice_id": invoice.pk,
                "redirect": {
                    "url": instructions.url,
                    "method": instructions.method,
                    "fields": instructions.fields,
                },
            }
        )


class SmsWalletTopupCallbackView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsOwner]

    def post(self, request, invoice_id: int):
        provider = request.data.get("provider")
        with system_context():
            invoice = get_object_or_404(
                SaasInvoice, pk=invoice_id, org=request.gym.org, kind=SaasInvoice.Kind.SMS_TOPUP
            )
            if invoice.status == SaasInvoice.Status.PAID:
                return Response({"status": "paid"})
            return _verify_and_confirm(invoice, provider, request)


class SupportTicketListView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsManagerOrAbove]

    def get(self, request):
        with system_context():
            tickets = list(
                SupportTicket.objects.filter(org=request.gym.org)
                .order_by("-updated_at")
                .values("id", "subject", "priority", "status", "created_at", "updated_at")
            )
        return Response(tickets)

    def post(self, request):
        subject = (request.data.get("subject") or "").strip()
        if not subject:
            return Response({"detail": "subject is required."}, status=400)
        with system_context():
            ticket = SupportTicket.objects.create(
                org=request.gym.org,
                subject=subject,
                priority=request.data.get("priority", SupportTicket.Priority.MEDIUM),
            )
            if request.data.get("message"):
                ticket.messages.create(author=request.user, body=request.data["message"])
        return Response({"id": ticket.pk}, status=status.HTTP_201_CREATED)


class SupportTicketMessageView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsManagerOrAbove]

    def post(self, request, ticket_id: int):
        body = (request.data.get("body") or "").strip()
        if not body:
            return Response({"detail": "body is required."}, status=400)
        with system_context():
            ticket = get_object_or_404(SupportTicket, pk=ticket_id, org=request.gym.org)
            ticket.messages.create(author=request.user, body=body)
        return Response(status=status.HTTP_201_CREATED)


class ExportDataView(APIView):
    """FR-11.7: triggers the Celery export; the signed link follows by
    email within the 24h window (saas/tasks.py::export_org_data_task).
    """

    permission_classes = [permissions.IsAuthenticated, IsOwner]

    def post(self, request):
        from saas.tasks import export_org_data_task

        export_org_data_task.delay(str(request.gym.org_id))
        return Response({"status": "queued"})


class DeleteAccountView(APIView):
    """FR-11.7: 30-day grace, then the daily sweep anonymizes members."""

    permission_classes = [permissions.IsAuthenticated, IsOwner]

    def post(self, request):
        with system_context():
            services.schedule_account_deletion(request.gym.org)
        return Response({"status": "scheduled"})


# ============================================================================
# Platform (FitKhata staff only) — /api/v1/platform/...
# ============================================================================


class TenantListView(APIView):
    """Plan, MRR, member count, last activity, a simple health score."""

    permission_classes = [permissions.IsAuthenticated, IsPlatformStaff]

    def get(self, request):
        from members.models import Member

        with system_context():
            subs = Subscription.objects.select_related("plan", "org")
            rows = []
            for sub in subs:
                member_count = Member.objects.filter(org=sub.org).count()
                last_active = (
                    Member.objects.filter(org=sub.org, last_check_in_at__isnull=False)
                    .order_by("-last_check_in_at")
                    .values_list("last_check_in_at", flat=True)
                    .first()
                )
                mrr = _plan_mrr(sub) if sub.status in _BILLING_STATUSES else Decimal("0")
                # A rough, legible score: full marks if active & under limit,
                # docked for dunning depth or being near the member cap.
                health = 100
                if sub.status == Subscription.Status.GRACE:
                    health -= 30
                elif sub.status in (Subscription.Status.READ_ONLY, Subscription.Status.SUSPENDED):
                    health -= 60
                if sub.plan.member_limit and member_count >= sub.plan.member_limit * 0.9:
                    health -= 10
                rows.append(
                    {
                        "org_id": str(sub.org_id),
                        "org_name": sub.org.name,
                        "plan_code": sub.plan.code,
                        "status": sub.status,
                        "mrr_npr": str(mrr),
                        "member_count": member_count,
                        "last_active_at": last_active,
                        "health_score": max(health, 0),
                    }
                )
        return Response(rows)


class MetricsView(APIView):
    """MRR, churn, trial-conversion — simple point-in-time aggregates, not
    a time series store (none exists for this yet; out of this phase's
    scope per the plan's "explicitly not building" list).
    """

    permission_classes = [permissions.IsAuthenticated, IsPlatformStaff]

    def get(self, request):
        with system_context():
            subs = list(Subscription.objects.select_related("plan"))
            mrr = sum(
                (_plan_mrr(s) for s in subs if s.status in _BILLING_STATUSES),
                Decimal("0"),
            )
            by_status = {
                row["status"]: row["n"]
                for row in Subscription.objects.values("status").annotate(n=Count("id"))
            }
            total = sum(by_status.values()) or 1
            churned = by_status.get(Subscription.Status.CANCELLED, 0) + by_status.get(
                Subscription.Status.SUSPENDED, 0
            )
            trials = by_status.get(Subscription.Status.TRIAL, 0)
            converted = sum(
                1
                for s in subs
                if s.status
                in (
                    Subscription.Status.ACTIVE,
                    Subscription.Status.GRACE,
                    Subscription.Status.READ_ONLY,
                )
            )
        return Response(
            {
                "mrr_npr": str(mrr),
                "churn_rate_pct": round(churned / total * 100, 1),
                "trial_conversion_pct": round(converted / max(trials + converted, 1) * 100, 1),
                "by_status": by_status,
            }
        )


class ImpersonateView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsPlatformStaff]

    def post(self, request):
        org_id = request.data.get("org_id")
        reason = (request.data.get("reason") or "").strip()
        if not reason:
            return Response({"detail": "A reason is required to impersonate."}, status=400)
        with system_context():
            org = get_object_or_404(Organization, pk=org_id)
            try:
                result = services.start_impersonation(request.user, org, reason)
            except ValueError as exc:
                return Response({"detail": str(exc)}, status=400)
        return Response(result)


class FeatureFlagListView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsPlatformStaff]

    def get(self, request):
        flags = list(
            FeatureFlag.objects.order_by("key").values(
                "id", "key", "default", "per_org_overrides", "rollout_pct"
            )
        )
        return Response(flags)

    def post(self, request):
        key = (request.data.get("key") or "").strip()
        if not key:
            return Response({"detail": "key is required."}, status=400)
        flag, _ = FeatureFlag.objects.update_or_create(
            key=key,
            defaults={
                "default": bool(request.data.get("default", False)),
                "rollout_pct": request.data.get("rollout_pct"),
                "per_org_overrides": request.data.get("per_org_overrides", {}),
            },
        )
        return Response({"id": flag.pk}, status=status.HTTP_201_CREATED)


class AnnouncementBroadcastView(APIView):
    """FR-11.6: sends immediately to every active owner across every org —
    no persisted "platform announcement" model, just the send + one audit
    row for traceability (not per-recipient).
    """

    permission_classes = [permissions.IsAuthenticated, IsPlatformStaff]

    def post(self, request):
        subject = (request.data.get("subject") or "").strip()
        body = (request.data.get("body") or "").strip()
        if not subject or not body:
            return Response({"detail": "subject and body are required."}, status=400)

        with system_context():
            owners = list(
                StaffRole.objects.filter(role=StaffRole.Role.OWNER, is_active=True).select_related(
                    "user"
                )
            )
            sent = 0
            for owner_role in owners:
                user = owner_role.user
                if user.email:
                    email_provider.send(user.email, subject, body)
                    sent += 1
                elif user.phone:
                    whatsapp_provider.send(
                        user.phone, "fitkhata_announcement", "en", [subject, body]
                    )
                    sent += 1
            services.log_platform_action(
                None, "announcement_broadcast", actor=request.user, after={"subject": subject}
            )
        return Response({"sent": sent})


class TicketInboxView(APIView):
    """Platform-wide ticket inbox — every org's tickets, not just one."""

    permission_classes = [permissions.IsAuthenticated, IsPlatformStaff]

    def get(self, request):
        with system_context():
            tickets = list(
                SupportTicket.objects.select_related("org")
                .order_by("-updated_at")
                .values(
                    "id", "org__name", "subject", "priority", "status", "created_at", "updated_at"
                )
            )
        return Response(tickets)


class MarkInvoicePaidBankView(APIView):
    """Manual bank-transfer confirmation, FR-11.3's "bank transfer marked
    by super admin" path — no gateway involved.
    """

    permission_classes = [permissions.IsAuthenticated, IsPlatformStaff]

    def post(self, request, invoice_id: int):
        with system_context():
            invoice = get_object_or_404(SaasInvoice, pk=invoice_id)
            services.confirm_saas_invoice_payment(invoice, paid_via="bank", actor=request.user)
        return Response({"status": "paid"})
