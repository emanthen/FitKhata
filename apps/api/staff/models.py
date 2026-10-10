"""Phase 9: staff employment, rostering, attendance, leave, advances, and
payroll. Distinct from accounts.StaffRole (who can log in as what) — these
models are payroll profile data (salary, bank, PAN), never auth.
"""

from __future__ import annotations

from django.contrib.postgres.fields import ArrayField
from django.db import models

from accounts.models import StaffRole
from core.models import TenantModel


class StaffCodeCounter(TenantModel):
    """One row per gym — select_for_update()'d inside register_staff_profile()
    to allocate the next badge_code without gaps or races. Same shape as
    members.MemberCodeCounter.
    """

    last_value = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["gym"], name="unique_gym_staff_code_counter"),
        ]

    def __str__(self) -> str:
        return f"{self.gym_id}: {self.last_value}"


class StaffProfile(TenantModel):
    """Payroll profile for one staff member at one gym. bank_account_encrypted
    and pan_no are owner-only visible (see staff/serializers.py) — rule 10's
    Fernet encryption, same core.crypto helper as Member.qr_secret.
    """

    class EmploymentType(models.TextChoices):
        MONTHLY = "monthly", "Monthly salary"
        HOURLY = "hourly", "Hourly wage"

    user = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="staff_profiles"
    )
    employment_type = models.CharField(max_length=20, choices=EmploymentType.choices)
    base_salary_npr = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    hourly_rate_npr = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    pan_no = models.CharField(max_length=20, blank=True)
    bank_name = models.CharField(max_length=100, blank=True)
    # Fernet ciphertext (core.crypto) — the plaintext account number never
    # touches the DB. Same pattern as Member.qr_secret.
    bank_account_encrypted = models.BinaryField(editable=False, blank=True, default=b"")
    joined_on = models.DateField()
    # STAFF- prefix keeps this structurally distinct from member_code's
    # f"{gym.code}-####" shape, so the gate kiosk/snapshot can never
    # confuse a staff badge for a member pass even by accident.
    badge_code = models.CharField(max_length=30)
    qr_secret = models.BinaryField(editable=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["gym", "user"], name="unique_gym_staff_user"),
            models.UniqueConstraint(fields=["gym", "badge_code"], name="unique_gym_badge_code"),
        ]

    def __str__(self) -> str:
        return f"{self.badge_code} ({self.user_id})"


class ShiftTemplate(TenantModel):
    """A recurring weekly slot (e.g. "Trainer, Mon 06:00-14:00") the roster
    is built from — StaffShift rows are the actual dated assignments.
    """

    WEEKDAY_CHOICES = [
        (0, "Monday"),
        (1, "Tuesday"),
        (2, "Wednesday"),
        (3, "Thursday"),
        (4, "Friday"),
        (5, "Saturday"),
        (6, "Sunday"),
    ]

    weekday = models.PositiveSmallIntegerField(choices=WEEKDAY_CHOICES)
    start = models.TimeField()
    end = models.TimeField()
    role = models.CharField(max_length=20, choices=StaffRole.Role.choices)

    def __str__(self) -> str:
        return f"{self.get_weekday_display()} {self.start}-{self.end} ({self.role})"


class StaffShift(TenantModel):
    """One dated roster assignment. Overlap conflicts are checked in
    staff.services.create_shift (domain.shifts.overlaps), not a DB
    constraint — two touching-but-not-overlapping shifts are legal.
    """

    staff = models.ForeignKey(StaffProfile, on_delete=models.CASCADE, related_name="shifts")
    date = models.DateField()
    start = models.TimeField()
    end = models.TimeField()
    template = models.ForeignKey(
        ShiftTemplate, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    def __str__(self) -> str:
        return f"{self.staff_id} {self.date} {self.start}-{self.end}"


class StaffAttendance(TenantModel):
    """clock_in/clock_out pair for one staff work session. Unlike member
    Attendance (one row per check-in event), this is paired — see
    staff.services.record_staff_checkins_batch for the open/close logic.
    """

    class Source(models.TextChoices):
        QR = "qr", "QR badge"
        BIOMETRIC = "biometric", "Biometric"
        MANUAL = "manual", "Manual"

    staff = models.ForeignKey(StaffProfile, on_delete=models.CASCADE, related_name="attendances")
    clock_in = models.DateTimeField()
    clock_out = models.DateTimeField(null=True, blank=True)
    source = models.CharField(max_length=20, choices=Source.choices)

    def __str__(self) -> str:
        return f"{self.staff_id} {self.clock_in}"


class LeaveRequest(TenantModel):
    class Kind(models.TextChoices):
        SICK = "sick", "Sick leave"
        CASUAL = "casual", "Casual leave"
        FESTIVAL = "festival", "Festival leave"
        UNPAID = "unpaid", "Unpaid leave"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    staff = models.ForeignKey(StaffProfile, on_delete=models.CASCADE, related_name="leave_requests")
    from_date = models.DateField()
    to_date = models.DateField()
    kind = models.CharField(max_length=20, choices=Kind.choices)
    reason = models.CharField(max_length=500, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    reviewed_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return f"{self.staff_id} {self.from_date}..{self.to_date} ({self.status})"


class LeaveBalance(TenantModel):
    """A plain balance row, manually provisioned (staff.services.
    adjust_leave_balance) and decremented on leave approval — no accrual
    scheduler; nobody asked for automatic monthly/annual accrual yet.
    """

    staff = models.ForeignKey(StaffProfile, on_delete=models.CASCADE, related_name="leave_balances")
    kind = models.CharField(max_length=20, choices=LeaveRequest.Kind.choices)
    days_available = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["staff", "kind"], name="unique_staff_leave_kind"),
        ]

    def __str__(self) -> str:
        return f"{self.staff_id} {self.kind}: {self.days_available}"


class PayrollRun(TenantModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        REVIEW = "review", "Review"
        FINALIZED = "finalized", "Finalized"

    period_bs = models.CharField(max_length=7)  # BS "YYYY-MM", e.g. "2083-06"
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    totals_npr = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    finalized_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    finalized_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["gym", "period_bs"], name="unique_gym_payroll_period"),
        ]

    def __str__(self) -> str:
        return f"{self.gym_id} {self.period_bs} ({self.status})"


class Advance(TenantModel):
    staff = models.ForeignKey(StaffProfile, on_delete=models.CASCADE, related_name="advances")
    amount_npr = models.DecimalField(max_digits=12, decimal_places=2)
    date = models.DateField()
    recovered_in_run = models.ForeignKey(
        PayrollRun, on_delete=models.SET_NULL, null=True, blank=True, related_name="advances"
    )

    def __str__(self) -> str:
        return f"{self.staff_id} {self.amount_npr} on {self.date}"


class Payslip(TenantModel):
    """No stored PDF — rendered fresh on request (staff.payslips.render_payslip_pdf),
    same stance billing.receipts.render_invoice_pdf takes for invoices:
    nothing here needs an immutable archived file distinct from "regenerate
    from DB state", and the run is already locked (immutable) at finalize.
    """

    run = models.ForeignKey(PayrollRun, on_delete=models.CASCADE, related_name="payslips")
    staff = models.ForeignKey(StaffProfile, on_delete=models.CASCADE, related_name="payslips")
    base_npr = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    commission_npr = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    incentives_npr = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    advances_npr = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tds_npr = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    social_security_npr = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    net_npr = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["run", "staff"], name="unique_run_staff_payslip"),
        ]

    def __str__(self) -> str:
        return f"{self.staff_id}@{self.run_id}: {self.net_npr}"


class ShiftChecklist(TenantModel):
    """A named template (e.g. "Opening", "Closing") — items is an ordered
    list of short strings, same ArrayField(CharField) shape as
    members.Member.tags; no child table needed for this.
    """

    name = models.CharField(max_length=100)
    items = ArrayField(models.CharField(max_length=200), default=list, blank=True)

    def __str__(self) -> str:
        return self.name


class ChecklistCompletion(TenantModel):
    checklist = models.ForeignKey(
        ShiftChecklist, on_delete=models.CASCADE, related_name="completions"
    )
    date = models.DateField()
    completed_by = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True)
    checked_items = ArrayField(models.CharField(max_length=200), default=list, blank=True)
    completed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["checklist", "date"], name="unique_checklist_completion_per_day"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.checklist_id}@{self.date}"
