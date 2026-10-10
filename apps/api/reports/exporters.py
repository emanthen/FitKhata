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


def rows_to_csv(rows: list[dict[str, Any]], fieldnames: list[str]) -> bytes:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue().encode("utf-8")


def rows_to_xlsx(
    rows: list[dict[str, Any]], fieldnames: list[str], labels: dict[str, str]
) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.append([labels.get(f, f) for f in fieldnames])
    for row in rows:
        ws.append([row.get(f) for f in fieldnames])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def render_vat_register_pdf(gym: Any, fiscal_year: int, register: dict[str, Any]) -> bytes:
    html = render_to_string(
        "reports/vat_register_pdf.html",
        {"gym": gym, "fiscal_year": fiscal_year, "rows": register["rows"]},
    )
    return HTML(string=html).write_pdf()
