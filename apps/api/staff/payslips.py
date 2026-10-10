"""Payslip PDF (WeasyPrint), Nepali/English — same stance as
billing.receipts.render_invoice_pdf: rendered fresh per request, nothing
persisted (see Payslip's own docstring on why).
"""

from __future__ import annotations

from django.template.loader import render_to_string
from weasyprint import HTML

from core.domain.bs import format_bs
from staff.models import Payslip

LABELS: dict[str, dict[str, str]] = {
    "en": {
        "title": "Payslip",
        "period": "Period",
        "employee": "Employee",
        "base": "Base pay",
        "commission": "Commission",
        "incentives": "Incentives",
        "advances": "Advances recovered",
        "tds": "TDS",
        "social_security": "Social security tax",
        "net": "Net pay",
    },
    "ne": {
        "title": "तलब पर्ची",
        "period": "अवधि",
        "employee": "कर्मचारी",
        "base": "आधारभूत तलब",
        "commission": "कमिसन",
        "incentives": "प्रोत्साहन",
        "advances": "अग्रिम कट्टी",
        "tds": "अग्रिम कर (टिडिएस)",
        "social_security": "सामाजिक सुरक्षा कर",
        "net": "खुद तलब",
    },
}


def render_payslip_pdf(payslip: Payslip, lang: str = "en") -> bytes:
    labels = LABELS.get(lang, LABELS["en"])
    html = render_to_string(
        "staff/payslip_pdf.html",
        {
            "payslip": payslip,
            "staff": payslip.staff,
            "run": payslip.run,
            "org": payslip.org,
            "gym": payslip.gym,
            "labels": labels,
            "generated_bs": format_bs(payslip.updated_at.date(), lang=lang),
        },
    )
    return HTML(string=html).write_pdf()
