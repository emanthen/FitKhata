from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

import pytest
from django.utils import timezone

from accounts.models import User
from billing.models import Invoice, Payment
from core.context import system_context
from gyms.models import Gym, Organization
from members.models import Member
from reports import exporters, services

pytestmark = pytest.mark.django_db


@pytest.fixture
def gym():
    with system_context():
        org = Organization.objects.create(name="Accounting Export Test Org")
        return Gym.objects.create(org=org, code="ACC1", name="Accounting Export Test Gym")


@pytest.fixture
def staff_user():
    with system_context():
        return User.objects.create_user(phone="+9779822000099", password="x")


def _make_member(gym) -> Member:
    return Member.objects.create(
        org=gym.org,
        gym=gym,
        member_code="ACC1-0001",
        full_name="Test Member",
        phone="+9779811112222",
        qr_secret=b"fixture-not-a-real-secret",
    )


def _make_invoice(gym, member, total: Decimal, taxable: Decimal, vat: Decimal) -> Invoice:
    return Invoice.objects.create(
        org=gym.org,
        gym=gym,
        number="2083-00001",
        fiscal_year=2083,
        status=Invoice.Status.ISSUED,
        member=member,
        subtotal_npr=taxable,
        taxable_npr=taxable,
        vat_npr=vat,
        total_npr=total,
    )


def _make_completed_payment(gym, member, amount, mode, staff, day: date, invoice=None) -> Payment:
    payment = Payment.objects.create(
        org=gym.org,
        gym=gym,
        member=member,
        invoice=invoice,
        mode=mode,
        channel=Payment.Channel.DESK,
        transaction_uuid=uuid.uuid4(),
        amount_npr=amount,
        status=Payment.Status.COMPLETED,
        collected_by=staff,
    )
    Payment.objects.filter(pk=payment.pk).update(
        created_at=timezone.make_aware(datetime.combine(day, datetime.min.time()))
    )
    return payment


def test_daily_journal_rows_splits_debit_and_credit_for_a_full_payment(gym, staff_user):
    today = timezone.localdate()
    with system_context():
        member = _make_member(gym)
        invoice = _make_invoice(
            gym, member, total=Decimal("1130.00"), taxable=Decimal("1000.00"), vat=Decimal("130.00")
        )
        _make_completed_payment(
            gym, member, Decimal("1130.00"), Payment.Mode.CASH, staff_user, today, invoice
        )

        rows = services.daily_journal_rows(gym, today)

    assert len(rows) == 3
    debit_row = next(r for r in rows if r["ledger"] == "Cash in hand")
    sales_row = next(r for r in rows if r["ledger"] == "Sales")
    vat_row = next(r for r in rows if r["ledger"] == "VAT Payable")

    assert debit_row["debit_npr"] == Decimal("1130.00")
    assert debit_row["credit_npr"] == Decimal("0.00")
    assert sales_row["credit_npr"] == Decimal("1000.00")
    assert vat_row["credit_npr"] == Decimal("130.00")

    # Debits and credits balance, same invariant any journal entry must hold.
    total_debit = sum((r["debit_npr"] for r in rows), Decimal("0.00"))
    total_credit = sum((r["credit_npr"] for r in rows), Decimal("0.00"))
    assert total_debit == total_credit == Decimal("1130.00")


def test_daily_journal_rows_splits_a_partial_payment_proportionally(gym, staff_user):
    today = timezone.localdate()
    with system_context():
        member = _make_member(gym)
        invoice = _make_invoice(
            gym, member, total=Decimal("2000.00"), taxable=Decimal("1769.91"), vat=Decimal("230.09")
        )
        # Half the invoice, paid today.
        _make_completed_payment(
            gym, member, Decimal("1000.00"), Payment.Mode.BANK, staff_user, today, invoice
        )

        rows = services.daily_journal_rows(gym, today)

    sales_row = next(r for r in rows if r["ledger"] == "Sales")
    vat_row = next(r for r in rows if r["ledger"] == "VAT Payable")

    assert sales_row["credit_npr"] == Decimal("884.96")  # 1769.91 * 0.5, ROUND_HALF_EVEN
    assert vat_row["credit_npr"] == Decimal("115.04")  # 230.09 * 0.5, ROUND_HALF_EVEN


def test_daily_journal_rows_falls_back_to_full_sales_when_no_invoice(gym, staff_user):
    today = timezone.localdate()
    with system_context():
        member = _make_member(gym)
        _make_completed_payment(
            gym, member, Decimal("500.00"), Payment.Mode.CASH, staff_user, today
        )

        rows = services.daily_journal_rows(gym, today)

    sales_row = next(r for r in rows if r["ledger"] == "Sales")
    assert sales_row["credit_npr"] == Decimal("500.00")
    assert not any(r["ledger"] == "VAT Payable" for r in rows)


def test_daily_journal_rows_only_includes_the_given_day(gym, staff_user):
    today = timezone.localdate()
    yesterday = today.replace(day=max(today.day - 1, 1))
    with system_context():
        member = _make_member(gym)
        _make_completed_payment(
            gym, member, Decimal("500.00"), Payment.Mode.CASH, staff_user, yesterday
        )

        rows = services.daily_journal_rows(gym, today)

    assert rows == []


# --- Tally / Swastik column mapping ---------------------------------------


def test_to_tally_rows_renames_columns():
    rows = [{"date": "2026-10-11", "voucher": "V1", "ledger": "Cash in hand",
             "debit_npr": Decimal("100.00"), "credit_npr": Decimal("0.00"), "narration": "x"}]

    mapped, fieldnames = exporters.to_tally_rows(rows)

    assert fieldnames == [
        "Date",
        "Voucher No",
        "Ledger",
        "Debit Amount",
        "Credit Amount",
        "Narration",
    ]
    assert mapped == [
        {
            "Date": "2026-10-11",
            "Voucher No": "V1",
            "Ledger": "Cash in hand",
            "Debit Amount": Decimal("100.00"),
            "Credit Amount": Decimal("0.00"),
            "Narration": "x",
        }
    ]


def test_to_swastik_rows_renames_columns():
    rows = [{"date": "2026-10-11", "voucher": "V1", "ledger": "Cash in hand",
             "debit_npr": Decimal("100.00"), "credit_npr": Decimal("0.00"), "narration": "x"}]

    mapped, fieldnames = exporters.to_swastik_rows(rows)

    assert fieldnames == ["Date", "Voucher No", "Particulars", "Dr Amount", "Cr Amount", "Remarks"]
    assert mapped[0]["Particulars"] == "Cash in hand"
    assert mapped[0]["Dr Amount"] == Decimal("100.00")
