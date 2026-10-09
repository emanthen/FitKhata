from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from billing.receipts import render_invoice_pdf, render_receipt_text
from core.context import system_context
from gyms.models import Gym, Organization
from members.models import Member, Plan
from members.services import sell_membership

pytestmark = pytest.mark.django_db


@pytest.fixture
def invoice():
    with system_context():
        org = Organization.objects.create(
            name="Receipt Test Org", pan_vat_no="123456789", is_vat_registered=True
        )
        gym = Gym.objects.create(org=org, code="RCPT1", name="Receipt Test Gym")
        plan = Plan.objects.create(
            org=org, gym=gym, name="Monthly", duration_days=30, price_npr=Decimal("3000.00")
        )
        member = Member.objects.create(
            org=org,
            gym=gym,
            member_code="RCPT1-0001",
            full_name="Receipt Test Member",
            phone="+9779800000001",
            qr_secret=b"fixture-not-a-real-secret",
        )
        membership = sell_membership(member, plan, today=date(2026, 1, 1))
        return membership.invoice


def test_render_invoice_pdf_produces_a_real_pdf(invoice):
    pdf_bytes = render_invoice_pdf(invoice)
    assert pdf_bytes.startswith(b"%PDF-")
    assert len(pdf_bytes) > 500  # not an empty/broken document


def test_render_receipt_text_includes_the_invoice_essentials(invoice):
    text = render_receipt_text(invoice)
    assert invoice.number in text
    assert "3000.00" in text
    assert "Receipt Test Gym" in text


def test_render_receipt_text_lines_fit_the_thermal_width(invoice):
    text = render_receipt_text(invoice)
    for line in text.split("\n"):
        assert len(line) <= 32
