"""CSV / XLSX / PDF export rendering. Mirrors billing/receipts.py's stance
(WeasyPrint, nothing persisted for synchronous exports) plus staff/
payslips.py's {"en": {...}, "ne": {...}} label-dict pattern for Nepali
headers (FR-10's own ask) — no new i18n mechanism invented for exports.
"""

from __future__ import annotations

import csv
import io
from typing import Any

from django.template.loader import render_to_string
from openpyxl import Workbook
from weasyprint import HTML

from core.domain.csv_safety import escape_formula_prefix

VAT_REGISTER_LABELS: dict[str, dict[str, str]] = {
    "en": {
        "bill_date_bs": "Bill date (BS)",
        "number": "Bill no.",
        "buyer_name": "Buyer name",
        "buyer_pan": "Buyer PAN",
        "taxable_npr": "Taxable amount",
        "vat_npr": "VAT",
        "total_npr": "Total",
    },
    "ne": {
        "bill_date_bs": "बिल मिति (वि.सं.)",
        "number": "बिल नं.",
        "buyer_name": "खरिदकर्ताको नाम",
        "buyer_pan": "खरिदकर्ता प्यान",
        "taxable_npr": "कर लाग्ने रकम",
        "vat_npr": "मू.अ.कर",
        "total_npr": "जम्मा",
    },
}

DUES_AGEING_LABELS: dict[str, dict[str, str]] = {
    "en": {"bucket": "Age bucket", "count": "Invoices", "total_npr": "Total due"},
    "ne": {"bucket": "उमेर समूह", "count": "बिलहरू", "total_npr": "जम्मा बाँकी"},
}


# FR-12.5: column layouts for the two accounting packages gyms in Nepal
# commonly use. Neither vendor publishes a single canonical import-CSV
# spec this project has in hand -- these are a best-effort generic
# voucher-import shape (Date/Voucher/Ledger/Debit/Credit/Narration),
# differing only in the header names each tool's own importer expects.
# Revisit against a real sample export from either tool if one surfaces.
TALLY_JOURNAL_FIELDS = {
    "date": "Date",
    "voucher": "Voucher No",
    "ledger": "Ledger",
    "debit_npr": "Debit Amount",
    "credit_npr": "Credit Amount",
    "narration": "Narration",
}

SWASTIK_JOURNAL_FIELDS = {
    "date": "Date",
    "voucher": "Voucher No",
    "ledger": "Particulars",
    "debit_npr": "Dr Amount",
    "credit_npr": "Cr Amount",
    "narration": "Remarks",
}


def _rename_journal_rows(
    rows: list[dict[str, Any]], column_map: dict[str, str]
) -> tuple[list[dict[str, Any]], list[str]]:
    renamed = [{column_map[key]: value for key, value in row.items()} for row in rows]
    return renamed, list(column_map.values())


def to_tally_rows(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    return _rename_journal_rows(rows, TALLY_JOURNAL_FIELDS)


def to_swastik_rows(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    return _rename_journal_rows(rows, SWASTIK_JOURNAL_FIELDS)


def rows_to_csv(rows: list[dict[str, Any]], fieldnames: list[str]) -> bytes:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows({k: escape_formula_prefix(v) for k, v in row.items()} for row in rows)
    return buf.getvalue().encode("utf-8")


def rows_to_xlsx(
    rows: list[dict[str, Any]], fieldnames: list[str], labels: dict[str, str]
) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.append([labels.get(f, f) for f in fieldnames])
    for row in rows:
        ws.append([escape_formula_prefix(row.get(f)) for f in fieldnames])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def render_vat_register_pdf(gym: Any, fiscal_year: int, register: dict[str, Any]) -> bytes:
    html = render_to_string(
        "reports/vat_register_pdf.html",
        {"gym": gym, "fiscal_year": fiscal_year, "rows": register["rows"]},
    )
    return HTML(string=html).write_pdf()
