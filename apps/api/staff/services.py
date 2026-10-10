"""Business logic for staff/payroll. Rule 9: views stay thin, this is where
it actually lives.
"""

from __future__ import annotations

import os
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.utils import timezone

from billing.models import Payment
from coaching.models import TrainerCommission
from core.crypto import encrypt_bytes
from core.domain.bs import month_range
from core.services import audit
from retention.models import RetentionCall
from staff.domain.attendance import is_late
from staff.domain.payroll import gross_pay, net_pay
from staff.domain.shifts import overlaps
from staff.domain.tax import compute_tds, load_slabs
from staff.models import (
    Advance,
    ChecklistCompletion,
    LeaveBalance,
    LeaveRequest,
    PayrollRun,
    Payslip,
    ShiftChecklist,
    StaffAttendance,
    StaffCodeCounter,
    StaffProfile,
    StaffShift,
)

ZERO = Decimal("0.00")


class ShiftConflict(ValueError):
    def __init__(self, conflicting_shift: StaffShift) -> None:
        self.conflicting_shift = conflicting_shift
        super().__init__(
            f"Overlaps an existing shift on {conflicting_shift.date} "
            f"({conflicting_shift.start}-{conflicting_shift.end})."
        )


class InsufficientLeaveBalance(ValueError):
    pass


class PayrollRunLocked(ValueError):
    pass


class SlabsNotConfirmed(ValueError):
    pass


def register_staff_profile(
    gym: Any, user: Any, actor: Any = None, **fields: Any
) -> StaffProfile:
    """Allocates the next badge_code under a row lock, same shape as
    members.services.register_member's member_code allocation.
    """
    with transaction.atomic():
        counter, _ = StaffCodeCounter.objects.select_for_update().get_or_create(
            org=gym.org, gym=gym
        )
        counter.last_value += 1
        counter.save(update_fields=["last_value"])
        badge_code = f"STAFF-{gym.code}-{counter.last_value:04d}"

        profile = StaffProfile.objects.create(
            org=gym.org,
            gym=gym,
            user=user,
            badge_code=badge_code,
            qr_secret=encrypt_bytes(os.urandom(32)),
            **fields,
        )
        audit(
            profile,
            "create",
            after={"badge_code": badge_code, "employment_type": profile.employment_type},
            actor=actor,
        )
        return profile


def _encrypt_bank_account(raw: str) -> bytes:
    return encrypt_bytes(raw.encode("utf-8")) if raw else b""


def create_shift(
    staff: StaffProfile,
    shift_date: date,
    start: Any,
    end: Any,
    template: Any = None,
) -> StaffShift:
    existing = StaffShift.objects.filter(staff=staff, date=shift_date)
    for other in existing:
        if overlaps((shift_date, start, end), (other.date, other.start, other.end)):
            raise ShiftConflict(other)

    return StaffShift.objects.create(
        org=staff.org,
        gym=staff.gym,
        staff=staff,
        date=shift_date,
        start=start,
        end=end,
        template=template,
    )


def record_staff_checkins_batch(rows: list[dict[str, Any]]) -> dict[str, list]:
    """Each row is {"staff": StaffProfile, "scanned_at": datetime}. An open
    StaffAttendance (clock_out IS NULL) for that staff member means this
    scan closes it; otherwise it opens a new one (and is checked for late
    arrival against that day's scheduled StaffShift, if any — see
    domain.attendance.is_late). Mirrors attendance.services.
    record_checkins_batch's accepted/rejected result shape.
    """
    accepted: list[dict[str, Any]] = []
    for row in rows:
        staff: StaffProfile = row["staff"]
        scanned_at: datetime = row["scanned_at"]
        open_attendance = (
            StaffAttendance.objects.filter(staff=staff, clock_out__isnull=True)
            .order_by("-clock_in")
            .first()
        )
        if open_attendance is not None:
            open_attendance.clock_out = scanned_at
            open_attendance.save(update_fields=["clock_out"])
            accepted.append({"id": open_attendance.pk, "late": None})
        else:
            attendance = StaffAttendance.objects.create(
                org=staff.org,
                gym=staff.gym,
                staff=staff,
                clock_in=scanned_at,
                source=StaffAttendance.Source.QR,
            )
            shift = StaffShift.objects.filter(staff=staff, date=scanned_at.date()).order_by(
                "start"
            ).first()
            late = staff_is_late(staff.gym, scanned_at, shift.start) if shift else None
            accepted.append({"id": attendance.pk, "late": late})
    return {"accepted": accepted}


def submit_leave_request(staff: StaffProfile, **fields: Any) -> LeaveRequest:
    return LeaveRequest.objects.create(org=staff.org, gym=staff.gym, staff=staff, **fields)


def approve_leave_request(leave_request: LeaveRequest, actor: Any = None) -> LeaveRequest:
    days = (leave_request.to_date - leave_request.from_date).days + 1

    with transaction.atomic():
        balance, _ = LeaveBalance.objects.select_for_update().get_or_create(
            staff=leave_request.staff,
            kind=leave_request.kind,
            defaults={"org": leave_request.org, "gym": leave_request.gym},
        )
        if balance.days_available < days:
            raise InsufficientLeaveBalance(
                f"Only {balance.days_available} {leave_request.kind} day(s) available, "
                f"this request needs {days}."
            )
        balance.days_available -= days
        balance.save(update_fields=["days_available"])

        leave_request.status = LeaveRequest.Status.APPROVED
        leave_request.reviewed_by = actor
        leave_request.reviewed_at = timezone.now()
        leave_request.save(update_fields=["status", "reviewed_by", "reviewed_at"])
        audit(leave_request, "update", after={"status": "approved"}, actor=actor)
    return leave_request


def reject_leave_request(leave_request: LeaveRequest, actor: Any = None) -> LeaveRequest:
    leave_request.status = LeaveRequest.Status.REJECTED
    leave_request.reviewed_by = actor
    leave_request.reviewed_at = timezone.now()
    leave_request.save(update_fields=["status", "reviewed_by", "reviewed_at"])
    audit(leave_request, "update", after={"status": "rejected"}, actor=actor)
    return leave_request


def adjust_leave_balance(
    staff: StaffProfile, kind: str, delta_days: Decimal, actor: Any = None
) -> LeaveBalance:
    """Manual provisioning/correction — no accrual scheduler exists; this
    is how a manager credits or corrects a balance.
    """
    with transaction.atomic():
        balance, _ = LeaveBalance.objects.select_for_update().get_or_create(
            staff=staff, kind=kind, defaults={"org": staff.org, "gym": staff.gym}
        )
        before = balance.days_available
        balance.days_available += delta_days
        balance.save(update_fields=["days_available"])
    audit(
        balance,
        "update",
        before={"days_available": str(before)},
        after={"days_available": str(balance.days_available)},
        actor=actor,
    )
    return balance


def create_advance(
    staff: StaffProfile, amount_npr: Decimal, advance_date: date, actor: Any = None
) -> Advance:
    advance = Advance.objects.create(
        org=staff.org, gym=staff.gym, staff=staff, amount_npr=amount_npr, date=advance_date
    )
    audit(advance, "create", after={"amount_npr": str(amount_npr)}, actor=actor)
    return advance


def _hours_worked(staff: StaffProfile, period_start: date, period_end: date) -> Decimal:
    attendances = StaffAttendance.objects.filter(
        staff=staff,
        clock_in__date__gte=period_start,
        clock_in__date__lte=period_end,
        clock_out__isnull=False,
    )
    total = Decimal("0")
    for a in attendances:
        assert a.clock_out is not None  # guaranteed by clock_out__isnull=False above
        total += Decimal((a.clock_out - a.clock_in).total_seconds()) / Decimal("3600")
    return total


def _commission_for_period(staff: StaffProfile, period_start: date, period_end: date) -> Decimal:
    ad_periods = {period_start.strftime("%Y-%m"), period_end.strftime("%Y-%m")}
    rows = TrainerCommission.objects.filter(
        trainer=staff.user, gym=staff.gym, period__in=ad_periods
    )
    total = ZERO
    for row in rows:
        total += row.amount_npr
    return total


def _advances_for_run(staff: StaffProfile, run: PayrollRun) -> Decimal:
    rows = Advance.objects.filter(staff=staff, recovered_in_run=run)
    total = ZERO
    for row in rows:
        total += row.amount_npr
    return total


def fiscal_year_for_period_bs(period_bs: str) -> str:
    """period_bs is BS 'YYYY-MM' — Nepali FY runs Shrawan (BS month 4) to
    the next Ashadh, same rule core.domain.nptime.fiscal_year() uses for
    an AD date, applied directly to the BS year/month already in hand.
    """
    bs_year, bs_month = (int(p) for p in period_bs.split("-"))
    fy_start_year = bs_year if bs_month >= 4 else bs_year - 1
    return f"{fy_start_year}/{(fy_start_year + 1) % 100:02d}"


def _compute_payslip_fields(
    staff: StaffProfile, run: PayrollRun, fiscal_year: str
) -> dict[str, Decimal]:
    bs_year, bs_month = (int(p) for p in run.period_bs.split("-"))
    period_start, period_end = month_range(bs_year, bs_month)

    if staff.employment_type == "hourly":
        hours = _hours_worked(staff, period_start, period_end)
    else:
        hours = Decimal("0")
    base = gross_pay(staff.employment_type, staff.base_salary_npr, staff.hourly_rate_npr, hours)
    commission = _commission_for_period(staff, period_start, period_end)
    advances = _advances_for_run(staff, run)

    annual_taxable = (base + commission) * Decimal("12")
    slabs = load_slabs(fiscal_year)
    tds = compute_tds(annual_taxable, slabs["slabs"]) / Decimal("12")
    social_security = ZERO  # the slab file's first band already covers this; no separate line

    return {
        "base_npr": base,
        "commission_npr": commission,
        "incentives_npr": ZERO,
        "advances_npr": advances,
        "tds_npr": tds.quantize(Decimal("0.01")),
        "social_security_npr": social_security,
    }


def create_payroll_run(gym: Any, period_bs: str, actor: Any = None) -> PayrollRun:
    """Computes and creates one Payslip per active StaffProfile immediately
    (not deferred to finalize), so the "review" step has real numbers.
    Re-running for an already-draft period recomputes in place; doing this
    on a finalized run is refused.
    """
    run, created = PayrollRun.objects.get_or_create(
        gym=gym, period_bs=period_bs, defaults={"org": gym.org}
    )
    if run.status == PayrollRun.Status.FINALIZED:
        raise PayrollRunLocked(f"Payroll run {period_bs} is already finalized.")

    fiscal_year = fiscal_year_for_period_bs(period_bs)
    with transaction.atomic():
        Payslip.objects.filter(run=run).delete()
        total = ZERO
        for staff in StaffProfile.objects.filter(gym=gym, is_active=True):
            fields = _compute_payslip_fields(staff, run, fiscal_year)
            net = net_pay(
                fields["base_npr"] + fields["commission_npr"],
                ZERO,
                fields["incentives_npr"],
                fields["advances_npr"],
                fields["tds_npr"],
                fields["social_security_npr"],
            )
            Payslip.objects.create(
                org=gym.org, gym=gym, run=run, staff=staff, net_npr=net, **fields
            )
            total += net
        run.totals_npr = total
        run.save(update_fields=["totals_npr"])

    audit(run, "create" if created else "update", after={"totals_npr": str(total)}, actor=actor)
    return run


def update_payslip_line(payslip: Payslip, actor: Any = None, **fields: Any) -> Payslip:
    """Lets a manager set the incentives line (no automatic source for it)
    before finalize. Refused once the run is locked.
    """
    if payslip.run.status == PayrollRun.Status.FINALIZED:
        raise PayrollRunLocked("This payroll run is already finalized.")

    before = {f: str(getattr(payslip, f)) for f in fields}
    for field, value in fields.items():
        setattr(payslip, field, value)
    payslip.net_npr = net_pay(
        payslip.base_npr + payslip.commission_npr,
        ZERO,
        payslip.incentives_npr,
        payslip.advances_npr,
        payslip.tds_npr,
        payslip.social_security_npr,
    )
    payslip.save(update_fields=[*fields.keys(), "net_npr"])
    audit(
        payslip,
        "update",
        before=before,
        after={f: str(getattr(payslip, f)) for f in fields},
        actor=actor,
    )
    return payslip


def finalize_payroll_run(run: PayrollRun, actor: Any = None) -> PayrollRun:
    fiscal_year = fiscal_year_for_period_bs(run.period_bs)
    slabs = load_slabs(fiscal_year)
    if not slabs.get("confirmed"):
        raise SlabsNotConfirmed(
            f"Tax slabs for {fiscal_year} are not yet confirmed by an owner — "
            "cannot finalize payroll against unconfirmed figures."
        )
    if run.status == PayrollRun.Status.FINALIZED:
        raise PayrollRunLocked(f"Payroll run {run.period_bs} is already finalized.")

    run.status = PayrollRun.Status.FINALIZED
    run.finalized_by = actor
    run.finalized_at = timezone.now()
    run.save(update_fields=["status", "finalized_by", "finalized_at"])
    audit(run, "update", after={"status": "finalized"}, actor=actor)
    return run


def submit_checklist_completion(
    checklist: ShiftChecklist,
    completion_date: date,
    checked_items: list[str],
    actor: Any = None,
) -> ChecklistCompletion:
    completion, _ = ChecklistCompletion.objects.update_or_create(
        checklist=checklist,
        date=completion_date,
        defaults={
            "org": checklist.org,
            "gym": checklist.gym,
            "checked_items": checked_items,
            "completed_by": actor,
        },
    )
    return completion


def staff_leaderboard(gym: Any, period_bs: str) -> list[dict[str, Any]]:
    """FR-9.7: per-staff counts for one BS period. "renewals sold" = desk
    payments this staff collected (billing.Payment.collected_by);
    "calls completed" = retention calls this staff finished; "saves" = the
    subset of those with outcome="coming_back" (the member confirmed
    they're staying) — this codebase's definition of a save, since the
    task doesn't specify one itself.
    """
    bs_year, bs_month = (int(p) for p in period_bs.split("-"))
    period_start, period_end = month_range(bs_year, bs_month)

    rows = []
    for staff in StaffProfile.objects.filter(gym=gym, is_active=True).select_related("user"):
        payments = Payment.objects.filter(
            gym=gym,
            collected_by=staff.user,
            status=Payment.Status.COMPLETED,
            created_at__date__gte=period_start,
            created_at__date__lte=period_end,
        )
        calls = RetentionCall.objects.filter(
            gym=gym,
            assigned_to=staff.user,
            completed_at__date__gte=period_start,
            completed_at__date__lte=period_end,
        )
        renewals_sold = payments.count()
        renewals_npr = ZERO
        for p in payments:
            renewals_npr += p.amount_npr
        calls_completed = calls.count()
        saves = calls.filter(outcome=RetentionCall.Outcome.COMING_BACK).count()

        rows.append(
            {
                "staff_id": staff.pk,
                "badge_code": staff.badge_code,
                "full_name": staff.user.full_name,
                "renewals_sold": renewals_sold,
                "renewals_npr": renewals_npr,
                "calls_completed": calls_completed,
                "saves": saves,
            }
        )
    return rows


def late_grace_minutes(gym: Any) -> int:
    return int(gym.settings.get("late_grace_min", 10))


def staff_is_late(gym: Any, clock_in: datetime, shift_start: Any) -> bool:
    return is_late(clock_in, shift_start, late_grace_minutes(gym))
