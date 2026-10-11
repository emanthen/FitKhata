"""Report queries, export orchestration, and owner-summary assembly. Rule 9:
views stay thin, this is where it actually lives. Every query here goes
through the *_scoped views (reports.models) — never the raw mv_* tables,
which have no tenant filtering of their own (see reports/migrations/0001's
docstring for why materialized views can't carry RLS and what the scoped
views do instead).
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from django.db.models import Sum
from django.utils import timezone

from billing.domain.shift import variance
from billing.models import CashShift, Invoice, Payment
from billing.services import shift_expected_cash_npr
from core.domain.bs import month_range
from members.models import Member, Membership
from reports.domain.ageing import bucket_dues_ageing
from reports.domain.vat_register import vat_register_monthly_totals, vat_register_rows
from reports.models import MVAttendanceHourly, MVCohortRetention, MVDailyRevenue, MVMembershipFlow

ZERO = Decimal("0.00")


class InvalidReportRange(ValueError):
    pass


def parse_date_range(from_: str, to_: str, calendar: str) -> tuple[date, date]:
    """calendar="ad": from_/to_ are ISO dates. calendar="bs": from_/to_ are
    BS "YYYY-MM" month strings, converted via core.domain.bs.month_range —
    `from_`'s month start and `to_`'s month end become the AD range.
    """
    if calendar == "ad":
        try:
            return date.fromisoformat(from_), date.fromisoformat(to_)
        except ValueError as exc:
            raise InvalidReportRange(f"Invalid AD date: {exc}") from exc
    if calendar == "bs":
        try:
            from_year, from_month = (int(p) for p in from_.split("-"))
            to_year, to_month = (int(p) for p in to_.split("-"))
            start, _ = month_range(from_year, from_month)
            _, end = month_range(to_year, to_month)
        except ValueError as exc:
            raise InvalidReportRange(f"Invalid BS month: {exc}") from exc
        return start, end
    raise InvalidReportRange(f"calendar must be 'ad' or 'bs', got {calendar!r}")


def revenue_trend(gym: Any, start: date, end: date) -> list[Any]:
    """Daily revenue totals in [start, end], for the "revenue trend" chart."""
    rows = (
        MVDailyRevenue.objects.filter(gym_id=gym.pk, day__gte=start, day__lte=end)
        .values("day")
        .annotate(amount_npr=Sum("amount_npr"), payment_count=Sum("payment_count"))
        .order_by("day")
    )
    return list(rows)


def plan_mix(gym: Any, start: date, end: date) -> list[Any]:
    """Revenue grouped by plan, for the "plan mix" chart."""
    rows = (
        MVDailyRevenue.objects.filter(
            gym_id=gym.pk, day__gte=start, day__lte=end, plan_id__isnull=False
        )
        .values("plan_id")
        .annotate(amount_npr=Sum("amount_npr"))
        .order_by("-amount_npr")
    )
    return list(rows)


def membership_flow(gym: Any, start: date, end: date) -> list[Any]:
    fields = ["day", "new_count", "renewed_count", "expired_count", "churned_count"]
    return list(
        MVMembershipFlow.objects.filter(gym_id=gym.pk, day__gte=start, day__lte=end)
        .values(*fields)
        .order_by("day")
    )


def attendance_heatmap(gym: Any) -> list[Any]:
    return list(
        MVAttendanceHourly.objects.filter(gym_id=gym.pk)
        .values("weekday", "hour", "count")
        .order_by("weekday", "hour")
    )


def cohort_retention(gym: Any) -> list[Any]:
    fields = [
        "join_month", "cohort_size", "retained_m1", "retained_m3", "retained_m6", "retained_m12"
    ]
    return list(
        MVCohortRetention.objects.filter(gym_id=gym.pk).values(*fields).order_by("join_month")
    )


def dues_ageing_report(gym: Any, today: date | None = None) -> dict[str, dict[str, Any]]:
    """FR-10.6: unpaid (draft) invoices bucketed 0-30/31-60/60+ by bill_date."""
    today = today or timezone.localdate()
    buckets: dict[str, dict[str, Any]] = {
        "0-30": {"count": 0, "total_npr": ZERO},
        "31-60": {"count": 0, "total_npr": ZERO},
        "60+": {"count": 0, "total_npr": ZERO},
    }
    invoices = Invoice.objects.filter(
        gym=gym, status=Invoice.Status.DRAFT, bill_date__isnull=False
    ).only("bill_date", "total_npr")
    for invoice in invoices:
        assert invoice.bill_date is not None  # guaranteed by bill_date__isnull=False above
        days_outstanding = (today - invoice.bill_date).days
        bucket = bucket_dues_ageing(days_outstanding)
        buckets[bucket]["count"] += 1
        buckets[bucket]["total_npr"] += invoice.total_npr
    return buckets


def vat_sales_register(gym: Any, fiscal_year: int) -> dict[str, Any]:
    """FR-10.7: IRD-format sales register for one fiscal year, reconciling
    exactly with Invoice totals (asserted in reports/tests/test_services.py).
    """
    invoices = list(
        Invoice.objects.filter(
            gym=gym, fiscal_year=fiscal_year, status=Invoice.Status.ISSUED
        ).order_by("bill_date_bs")
    )
    return {
        "rows": vat_register_rows(invoices),
        "monthly_totals": vat_register_monthly_totals(invoices),
    }


_CASH_CLEARING_LEDGER: dict[str, str] = {
    Payment.Mode.CASH: "Cash in hand",
    Payment.Mode.BANK: "Bank",
    Payment.Mode.CHEQUE: "Bank",
    Payment.Mode.ESEWA: "eSewa clearing",
    Payment.Mode.MANUAL_ESEWA: "eSewa clearing",
    Payment.Mode.KHALTI: "Khalti clearing",
    Payment.Mode.FONEPAY: "Fonepay clearing",
}


def daily_journal_rows(gym: Any, day: date) -> list[dict[str, Any]]:
    """FR-12.5: one debit + one-or-two credit rows per completed payment on
    `day` -- debit the clearing ledger for however the member paid, credit
    Sales (+ VAT Payable, if the related invoice has any) for however much
    of that invoice this payment actually covers. ponytail: splits credit
    amounts proportionally to this payment's share of its invoice's total,
    so a sequence of partial payments against one invoice sums correctly
    without double-booking -- it does not reconcile refunds/voids, which
    this phase doesn't track per-payment yet (see billing.services's own
    shift_expected_cash_npr docstring for the same caveat).
    """
    payments = (
        Payment.objects.filter(gym=gym, status=Payment.Status.COMPLETED, created_at__date=day)
        .select_related("invoice")
        .order_by("created_at")
    )

    rows: list[dict[str, Any]] = []
    for payment in payments:
        voucher = payment.receipt_no or str(payment.transaction_uuid)
        debit_ledger = _CASH_CLEARING_LEDGER.get(payment.mode, "Bank")
        narration = f"Payment {voucher} via {payment.get_mode_display()}"

        rows.append(
            {
                "date": day.isoformat(),
                "voucher": voucher,
                "ledger": debit_ledger,
                "debit_npr": payment.amount_npr,
                "credit_npr": ZERO,
                "narration": narration,
            }
        )

        invoice = payment.invoice
        if invoice is not None and invoice.total_npr > 0:
            ratio = payment.amount_npr / invoice.total_npr
            taxable_share = (invoice.taxable_npr * ratio).quantize(Decimal("0.01"))
            vat_share = (invoice.vat_npr * ratio).quantize(Decimal("0.01"))
        else:
            taxable_share, vat_share = payment.amount_npr, ZERO

        rows.append(
            {
                "date": day.isoformat(),
                "voucher": voucher,
                "ledger": "Sales",
                "debit_npr": ZERO,
                "credit_npr": taxable_share,
                "narration": narration,
            }
        )
        if vat_share > 0:
            rows.append(
                {
                    "date": day.isoformat(),
                    "voucher": voucher,
                    "ledger": "VAT Payable",
                    "debit_npr": ZERO,
                    "credit_npr": vat_share,
                    "narration": narration,
                }
            )

    return rows


def dashboard_summary(gym: Any, renewals_due_days: int = 7) -> dict[str, Any]:
    """FR-10's owner dashboard, as one combined query set (not five separate
    endpoints) so the page loads in one round trip. Live occupancy is
    deliberately NOT here — it arrives over the already-existing websocket
    (attendance.consumers.GymFeedConsumer), not this HTTP response.
    """
    today = timezone.localdate()
    month_start = today.replace(day=1)

    active_members = Member.objects.filter(gym=gym, status=Member.Status.ACTIVE).count()

    revenue_today = (
        MVDailyRevenue.objects.filter(gym_id=gym.pk, day=today).aggregate(total=Sum("amount_npr"))[
            "total"
        ]
        or ZERO
    )
    revenue_month = (
        MVDailyRevenue.objects.filter(
            gym_id=gym.pk, day__gte=month_start, day__lte=today
        ).aggregate(total=Sum("amount_npr"))["total"]
        or ZERO
    )

    renewals_due = Membership.objects.filter(
        gym=gym,
        status=Membership.Status.ACTIVE,
        expiry_date__gte=today,
        expiry_date__lte=today + timedelta(days=renewals_due_days),
    ).count()

    red_list_count = Member.objects.filter(gym=gym, risk_state=Member.RiskState.RED_LIST).count()

    return {
        "active_members": active_members,
        "revenue_today_npr": revenue_today,
        "revenue_month_npr": revenue_month,
        "renewals_due": renewals_due,
        "red_list_count": red_list_count,
    }


def cash_variance_for_day(gym: Any, day: date) -> Decimal:
    shifts = CashShift.objects.filter(gym=gym, closed_at__date=day, counted_cash_npr__isnull=False)
    total = ZERO
    for shift in shifts:
        assert shift.counted_cash_npr is not None  # guaranteed by the filter above
        total += variance(shift_expected_cash_npr(shift), shift.counted_cash_npr)
    return total


def assemble_owner_summary(gym: Any, day: date) -> dict[str, Any]:
    """FR-10.8: the 21:00 summary's content — revenue by mode, new/renewed/
    expired counts, red list count, cash variance. Sending it (WhatsApp/
    email) is reports.tasks.send_owner_daily_summary's job, not this
    function's — this only assembles the numbers.
    """
    revenue_by_mode = dict(
        MVDailyRevenue.objects.filter(gym_id=gym.pk, day=day)
        .values("mode")
        .annotate(total=Sum("amount_npr"))
        .values_list("mode", "total")
    )
    flow = MVMembershipFlow.objects.filter(gym_id=gym.pk, day=day).first()

    return {
        "day": day,
        "revenue_by_mode": revenue_by_mode,
        "new_count": flow.new_count if flow else 0,
        "renewed_count": flow.renewed_count if flow else 0,
        "expired_count": flow.expired_count if flow else 0,
        "red_list_count": Member.objects.filter(
            gym=gym, risk_state=Member.RiskState.RED_LIST
        ).count(),
        "cash_variance_npr": cash_variance_for_day(gym, day),
    }
