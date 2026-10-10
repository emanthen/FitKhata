from dataclasses import dataclass
from decimal import Decimal

from reports.domain.vat_register import vat_register_monthly_totals, vat_register_rows


@dataclass
class FakeInvoice:
    bill_date_bs: str
    number: str
    buyer_name: str
    buyer_pan: str
    taxable_npr: Decimal
    vat_npr: Decimal
    total_npr: Decimal


INVOICES = [
    FakeInvoice(
        "2083-06-01", "2083-00001", "A", "PAN1",
        Decimal("1000.00"), Decimal("130.00"), Decimal("1130.00"),
    ),
    FakeInvoice(
        "2083-06-15", "2083-00002", "B", "PAN2",
        Decimal("2000.00"), Decimal("260.00"), Decimal("2260.00"),
    ),
    FakeInvoice(
        "2083-07-01", "2083-00003", "C", "PAN3",
        Decimal("500.00"), Decimal("65.00"), Decimal("565.00"),
    ),
]


def test_rows_preserve_order_and_fields() -> None:
    rows = vat_register_rows(INVOICES)
    assert len(rows) == 3
    assert rows[0]["number"] == "2083-00001"
    assert rows[0]["vat_npr"] == Decimal("130.00")


def test_monthly_totals_group_by_bs_month() -> None:
    totals = vat_register_monthly_totals(INVOICES)
    assert set(totals) == {"2083-06", "2083-07"}
    assert totals["2083-06"]["taxable_npr"] == Decimal("3000.00")
    assert totals["2083-06"]["vat_npr"] == Decimal("390.00")
    assert totals["2083-07"]["taxable_npr"] == Decimal("500.00")


def test_empty_input_has_no_totals() -> None:
    assert vat_register_monthly_totals([]) == {}
    assert vat_register_rows([]) == []
