from __future__ import annotations

from decimal import Decimal

import pytest

from billing.models import Product, Sale, SaleLine
from billing.services import InsufficientStock, SaleLineInput, record_pos_sale
from core.context import system_context
from gyms.models import Gym, Organization
from members.models import Member

pytestmark = pytest.mark.django_db


@pytest.fixture
def gym():
    with system_context():
        org = Organization.objects.create(name="POS Test Org")
        return Gym.objects.create(org=org, code="POS1", name="POS Test Gym")


@pytest.fixture
def member(gym):
    with system_context():
        return Member.objects.create(
            org=gym.org,
            gym=gym,
            member_code="POS1-0001",
            full_name="Test Member",
            phone="+9779800000011",
            qr_secret=b"not-a-real-secret-just-fixture-bytes",
        )


def _make_product(gym, sku="PROT-1KG", price=Decimal("1200.00"), stock=10) -> Product:
    return Product.objects.create(
        org=gym.org, gym=gym, sku=sku, name="Whey Protein 1kg", price_npr=price, stock_qty=stock
    )


def test_record_pos_sale_creates_invoice_and_sale(gym, member):
    with system_context():
        product = _make_product(gym)

        sale = record_pos_sale(gym, member, [SaleLineInput(product_id=product.pk, quantity=2)])

    with system_context():
        sale = Sale.objects.select_related("invoice").get(pk=sale.pk)
        assert sale.invoice.total_npr == Decimal("2400.00")
        assert sale.invoice.member_id == member.pk

        line = SaleLine.objects.get(sale=sale)
        assert line.quantity == 2
        assert line.unit_price_npr == Decimal("1200.00")
        assert line.line_total_npr == Decimal("2400.00")


def test_record_pos_sale_decrements_stock(gym, member):
    with system_context():
        product = _make_product(gym, stock=10)

        record_pos_sale(gym, member, [SaleLineInput(product_id=product.pk, quantity=3)])

        product.refresh_from_db()
    assert product.stock_qty == 7


def test_record_pos_sale_rejects_insufficient_stock(gym, member):
    with system_context():
        product = _make_product(gym, stock=1)

        with pytest.raises(InsufficientStock):
            record_pos_sale(gym, member, [SaleLineInput(product_id=product.pk, quantity=5)])

        product.refresh_from_db()
    # Nothing committed -- the whole sale (including the stock check for
    # any OTHER line in the same basket) rolls back together.
    assert product.stock_qty == 1
    with system_context():
        assert Sale.objects.count() == 0


def test_record_pos_sale_rejects_an_inactive_product(gym, member):
    with system_context():
        product = _make_product(gym)
        product.is_active = False
        product.save(update_fields=["is_active"])

        with pytest.raises(InsufficientStock):
            record_pos_sale(gym, member, [SaleLineInput(product_id=product.pk, quantity=1)])


def test_record_pos_sale_splits_vat_when_the_org_is_vat_registered(gym, member):
    """Regression guard: billing.domain.vat was fully built and tested in
    isolation but never actually wired into invoice creation -- every
    invoice (POS included) carried taxable_npr=vat_npr=0 regardless of the
    org's VAT registration. See create_draft_invoice's own docstring for
    the fix and why it's always a total_npr back-split, never an
    on-top addition.
    """
    with system_context():
        gym.org.is_vat_registered = True
        gym.org.save(update_fields=["is_vat_registered"])
        product = _make_product(gym, price=Decimal("1130.00"), stock=5)

        sale = record_pos_sale(gym, member, [SaleLineInput(product_id=product.pk, quantity=1)])

    with system_context():
        sale = Sale.objects.select_related("invoice").get(pk=sale.pk)
        assert sale.invoice.taxable_npr == Decimal("1000.00")
        assert sale.invoice.vat_npr == Decimal("130.00")
        assert sale.invoice.taxable_npr + sale.invoice.vat_npr == sale.invoice.total_npr


def test_record_pos_sale_handles_multiple_lines(gym, member):
    with system_context():
        protein = _make_product(gym, sku="PROT-1KG", price=Decimal("1200.00"), stock=5)
        gloves = _make_product(gym, sku="GLOVES-M", price=Decimal("450.00"), stock=5)

        sale = record_pos_sale(
            gym,
            member,
            [
                SaleLineInput(product_id=protein.pk, quantity=1),
                SaleLineInput(product_id=gloves.pk, quantity=2),
            ],
        )

    with system_context():
        sale = Sale.objects.select_related("invoice").get(pk=sale.pk)
        assert sale.invoice.total_npr == Decimal("2100.00")  # 1200 + 2*450
        assert SaleLine.objects.filter(sale=sale).count() == 2
