"""Invoice PDF (WeasyPrint, IRD-leaning format) and an 80mm receipt text
template. The real ESC/POS *byte* protocol (cut command, bold, etc.) is
apps/bridge's job in Phase 12 — this only produces the printable text
content bridge will eventually wrap in those commands; until then, the
admin UI prints this same content via the browser's own window.print() as
a plain fallback (billing/views.py's InvoiceReceiptTextView).
"""

from __future__ import annotations

from django.template.loader import render_to_string
from weasyprint import HTML

from billing.models import Invoice

RECEIPT_WIDTH = 32  # conservative char width for an 80mm thermal printer


def render_invoice_pdf(invoice: Invoice) -> bytes:
    html = render_to_string(
        "billing/invoice_pdf.html",
        {
            "invoice": invoice,
            "org": invoice.org,
            "gym": invoice.gym,
            "fiscal_year_short": f"{(invoice.fiscal_year + 1) % 100:02d}",
        },
    )
    return HTML(string=html).write_pdf()


def _line(left: str, right: str, width: int = RECEIPT_WIDTH) -> str:
    pad = max(1, width - len(left) - len(right))
    return f"{left}{' ' * pad}{right}"


def render_receipt_text(invoice: Invoice) -> str:
    lines = [
        invoice.gym.name.center(RECEIPT_WIDTH),
        "-" * RECEIPT_WIDTH,
        f"Invoice: {invoice.number}",
        f"Date: {invoice.bill_date} ({invoice.bill_date_bs} BS)",
        f"Member: {invoice.member.member_code}",
        "-" * RECEIPT_WIDTH,
    ]
    for item in invoice.lines.all():
        lines.append(item.description[:RECEIPT_WIDTH])
        lines.append(_line(f"  {item.quantity} x {item.unit_price_npr}", str(item.line_total_npr)))
    lines.append("-" * RECEIPT_WIDTH)
    lines.append(_line("Subtotal", str(invoice.subtotal_npr)))
    if invoice.discount_npr:
        lines.append(_line("Discount", f"-{invoice.discount_npr}"))
    if invoice.org.is_vat_registered:
        lines.append(_line("VAT (13%)", str(invoice.vat_npr)))
    lines.append(_line("TOTAL", f"NPR {invoice.total_npr}"))
    lines.append("=" * RECEIPT_WIDTH)
    lines.append("Thank you!".center(RECEIPT_WIDTH))
    return "\n".join(lines)
