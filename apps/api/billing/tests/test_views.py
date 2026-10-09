"""HTTP-level tests through DRF's APIClient — same reasoning as
members/tests/test_views.py: exercises routing/permissions/serializers
together, not just the service functions directly.
"""

from __future__ import annotations

import json
import uuid
from datetime import date
from decimal import Decimal
from unittest.mock import Mock, patch

import pytest
from rest_framework.test import APIClient

from accounts.models import StaffRole, User
from accounts.tokens import issue_tokens_for_user
from billing.models import CashShift, CreditNote, GatewayCredential, Payment
from core.context import system_context
from core.crypto import encrypt_bytes
from gyms.models import Gym, Organization
from members.models import AddOn, Member, Plan, PromoCode
from members.services import sell_membership

pytestmark = pytest.mark.django_db


def _client_for(user: User, gym: Gym) -> APIClient:
    tokens = issue_tokens_for_user(user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}", HTTP_X_GYM_ID=str(gym.pk))
    return client


@pytest.fixture
def owner_setup():
    with system_context():
        org = Organization.objects.create(name="Billing API Test Org")
        gym = Gym.objects.create(org=org, code="BAPI1", name="Billing API Test Gym")
        owner = User.objects.create_user(phone="+9774000000001", password="x")
        StaffRole.objects.create(user=owner, org=org, gym=gym, role=StaffRole.Role.OWNER)
        front_desk = User.objects.create_user(phone="+9774000000002", password="x")
        StaffRole.objects.create(
            user=front_desk, org=org, gym=gym, role=StaffRole.Role.FRONT_DESK
        )
        plan = Plan.objects.create(
            org=org, gym=gym, name="Monthly", duration_days=30, price_npr=Decimal("3000.00")
        )
        member = Member.objects.create(
            org=org,
            gym=gym,
            member_code="BAPI1-0001",
            full_name="Test Member",
            phone="+9779800000099",
            qr_secret=b"fixture-not-a-real-secret",
        )
    return org, gym, owner, front_desk, plan, member


# --- GatewayCredentialViewSet: owner-only -----------------------------------


def test_owner_can_create_a_gateway_credential_and_secret_is_never_returned(owner_setup):
    _org, gym, owner, _front_desk, _plan, _member = owner_setup
    client = _client_for(owner, gym)

    response = client.post(
        "/api/v1/gateway-credentials/",
        {
            "provider": "esewa",
            "environment": "sandbox",
            "merchant_code": "EPAYTEST",
            "secret": "8gBm/:&EnhH.1/q",
        },
        format="json",
    )

    assert response.status_code == 201, response.content
    body = response.json()
    assert body["is_configured"] is True
    assert "secret" not in body
    with system_context():
        stored = GatewayCredential.objects.get(pk=body["id"])
        assert bytes(stored.secret_encrypted) != b"8gBm/:&EnhH.1/q"  # encrypted, not plaintext


def test_front_desk_cannot_create_a_gateway_credential(owner_setup):
    _org, gym, _owner, front_desk, _plan, _member = owner_setup
    client = _client_for(front_desk, gym)

    response = client.post(
        "/api/v1/gateway-credentials/",
        {"provider": "esewa", "merchant_code": "EPAYTEST", "secret": "x"},
        format="json",
    )

    assert response.status_code == 403


# --- CollectPaymentView ------------------------------------------------------


def test_front_desk_collects_a_full_cash_payment_and_invoice_issues(owner_setup):
    _org, gym, _owner, front_desk, plan, member = owner_setup
    with system_context():
        membership = sell_membership(member, plan, today=date(2026, 1, 1))
        invoice_id = membership.invoice_id

    client = _client_for(front_desk, gym)
    response = client.post(
        "/api/v1/billing/payments",
        {"invoice_id": invoice_id, "mode": "cash", "amount_npr": "3000.00"},
        format="json",
    )

    assert response.status_code == 201, response.content
    assert response.json()["status"] == "completed"
    with system_context():
        from billing.models import Invoice

        assert Invoice.objects.get(pk=invoice_id).status == Invoice.Status.ISSUED


def test_partial_cash_payment_leaves_invoice_as_draft(owner_setup):
    _org, gym, _owner, front_desk, plan, member = owner_setup
    with system_context():
        membership = sell_membership(member, plan, today=date(2026, 1, 1))
        invoice_id = membership.invoice_id

    client = _client_for(front_desk, gym)
    response = client.post(
        "/api/v1/billing/payments",
        {"invoice_id": invoice_id, "mode": "cash", "amount_npr": "1000.00"},
        format="json",
    )

    assert response.status_code == 201, response.content
    with system_context():
        from billing.models import Invoice

        assert Invoice.objects.get(pk=invoice_id).status == Invoice.Status.DRAFT


# --- Cash shifts --------------------------------------------------------------


def test_shift_open_then_close_computes_variance(owner_setup):
    _org, gym, _owner, front_desk, plan, member = owner_setup
    client = _client_for(front_desk, gym)

    open_response = client.post(
        "/api/v1/billing/shifts", {"opening_float_npr": "5000.00"}, format="json"
    )
    assert open_response.status_code == 201, open_response.content
    shift_id = open_response.json()["id"]

    with system_context():
        membership = sell_membership(member, plan, today=date(2026, 1, 1))

    client.post(
        "/api/v1/billing/payments",
        {
            "invoice_id": membership.invoice_id,
            "mode": "cash",
            "amount_npr": "3000.00",
            "shift_id": shift_id,
        },
        format="json",
    )

    close_response = client.post(
        f"/api/v1/billing/shifts/{shift_id}/close",
        {"counted_cash_npr": "7850.00", "denominations": {"1000": 7, "100": 8, "50": 1}},
        format="json",
    )

    assert close_response.status_code == 200, close_response.content
    body = close_response.json()
    # expected = 5000 float + 3000 cash = 8000; counted 7850 -> variance -150
    assert body["expected_cash_npr"] == "8000.00"
    assert body["variance_npr"] == "-150.00"

    with system_context():
        shift = CashShift.objects.get(pk=shift_id)
        assert shift.closed_at is not None


def test_cannot_close_an_already_closed_shift(owner_setup):
    _org, gym, _owner, front_desk, _plan, _member = owner_setup
    client = _client_for(front_desk, gym)
    shift_id = client.post(
        "/api/v1/billing/shifts", {"opening_float_npr": "1000.00"}, format="json"
    ).json()["id"]

    first = client.post(
        f"/api/v1/billing/shifts/{shift_id}/close",
        {"counted_cash_npr": "1000.00"},
        format="json",
    )
    assert first.status_code == 200

    second = client.post(
        f"/api/v1/billing/shifts/{shift_id}/close",
        {"counted_cash_npr": "1000.00"},
        format="json",
    )
    assert second.status_code == 400


# --- Settlement report --------------------------------------------------------


def test_settlement_report_sums_completed_payments_by_mode(owner_setup):
    _org, gym, _owner, front_desk, plan, member = owner_setup
    client = _client_for(front_desk, gym)

    with system_context():
        membership = sell_membership(member, plan, today=date(2026, 1, 1))

    client.post(
        "/api/v1/billing/payments",
        {"invoice_id": membership.invoice_id, "mode": "cash", "amount_npr": "3000.00"},
        format="json",
    )

    today_str = date.today().isoformat()
    response = client.get(f"/api/v1/billing/settlement-report?date={today_str}")

    assert response.status_code == 200, response.content
    body = response.json()
    assert body["by_mode"]["cash"] == "3000.00"
    assert body["total_npr"] == "3000.00"

    with system_context():
        actual_sum = sum(
            (p.amount_npr for p in Payment.objects.filter(gym=gym, status="completed")),
            Decimal("0.00"),
        )
    assert Decimal(body["total_npr"]) == actual_sum


# --- Credit notes: owner approval required (FR-4.8) ---------------------------


def test_front_desk_can_request_but_not_approve_a_credit_note(owner_setup):
    _org, gym, owner, front_desk, plan, member = owner_setup
    with system_context():
        membership = sell_membership(member, plan, today=date(2026, 1, 1))

    fd_client = _client_for(front_desk, gym)
    create_response = fd_client.post(
        "/api/v1/credit-notes/",
        {
            "invoice": membership.invoice_id,
            "amount_npr": "500.00",
            "reason": "Member disputed a charge",
        },
        format="json",
    )
    assert create_response.status_code == 201, create_response.content
    credit_note_id = create_response.json()["id"]

    denied = fd_client.post(f"/api/v1/credit-notes/{credit_note_id}/approve/")
    assert denied.status_code == 403

    owner_client = _client_for(owner, gym)
    approved = owner_client.post(f"/api/v1/credit-notes/{credit_note_id}/approve/")
    assert approved.status_code == 200, approved.content
    assert approved.json()["approved_by"] is not None

    with system_context():
        note = CreditNote.objects.get(pk=credit_note_id)
        assert note.approved_by_id == owner.pk


def test_cannot_approve_the_same_credit_note_twice(owner_setup):
    _org, gym, owner, front_desk, plan, member = owner_setup
    with system_context():
        membership = sell_membership(member, plan, today=date(2026, 1, 1))

    fd_client = _client_for(front_desk, gym)
    credit_note_id = fd_client.post(
        "/api/v1/credit-notes/",
        {"invoice": membership.invoice_id, "amount_npr": "100.00", "reason": "test"},
        format="json",
    ).json()["id"]

    owner_client = _client_for(owner, gym)
    owner_client.post(f"/api/v1/credit-notes/{credit_note_id}/approve/")
    second = owner_client.post(f"/api/v1/credit-notes/{credit_note_id}/approve/")

    assert second.status_code == 400


# --- Gym/Org settings (IsOwner) ------------------------------------------------


def test_owner_can_update_vat_inclusive_pricing(owner_setup):
    org, gym, owner, _front_desk, _plan, _member = owner_setup
    client = _client_for(owner, gym)

    response = client.patch(
        "/api/v1/orgs/settings", {"vat_inclusive_pricing": True}, format="json"
    )

    assert response.status_code == 200, response.content
    assert response.json()["vat_inclusive_pricing"] is True
    with system_context():
        org.refresh_from_db()
        assert org.vat_inclusive_pricing is True


def test_invoice_rejects_raw_update_and_delete(owner_setup):
    """Regression: InvoiceViewSet must stay read-only (+ its one controlled
    `void` action) — a stray full-CRUD base class would let a client
    rewrite an invoice's total or delete it outright, bypassing
    create_draft_invoice's gapless numbering and collect_payment's audit
    trail entirely (rule 7).
    """
    _org, gym, _owner, front_desk, plan, member = owner_setup
    with system_context():
        membership = sell_membership(member, plan, today=date(2026, 1, 1))

    client = _client_for(front_desk, gym)
    patch_response = client.patch(
        f"/api/v1/invoices/{membership.invoice_id}/",
        {"total_npr": "1.00"},
        format="json",
    )
    delete_response = client.delete(f"/api/v1/invoices/{membership.invoice_id}/")

    assert patch_response.status_code == 405
    assert delete_response.status_code == 405


def test_credit_note_rejects_raw_update_and_delete(owner_setup):
    """Same reasoning as the invoice regression test above, for credit
    notes: no editing the amount out from under an owner's approval, no
    deleting the record.
    """
    _org, gym, _owner, front_desk, plan, member = owner_setup
    with system_context():
        membership = sell_membership(member, plan, today=date(2026, 1, 1))

    client = _client_for(front_desk, gym)
    credit_note_id = client.post(
        "/api/v1/credit-notes/",
        {"invoice": membership.invoice_id, "amount_npr": "100.00", "reason": "test"},
        format="json",
    ).json()["id"]

    patch_response = client.patch(
        f"/api/v1/credit-notes/{credit_note_id}/", {"amount_npr": "99999.00"}, format="json"
    )
    delete_response = client.delete(f"/api/v1/credit-notes/{credit_note_id}/")

    assert patch_response.status_code == 405
    assert delete_response.status_code == 405


def test_owner_can_void_an_invoice_with_a_reason(owner_setup):
    _org, gym, owner, _front_desk, plan, member = owner_setup
    with system_context():
        membership = sell_membership(member, plan, today=date(2026, 1, 1))

    client = _client_for(owner, gym)
    response = client.post(
        f"/api/v1/invoices/{membership.invoice_id}/void/",
        {"reason": "Duplicate sale, member already had an active plan"},
        format="json",
    )

    assert response.status_code == 200, response.content
    body = response.json()
    assert body["status"] == "void"
    assert "Duplicate sale" in body["void_reason"]


def test_void_requires_a_reason(owner_setup):
    _org, gym, owner, _front_desk, plan, member = owner_setup
    with system_context():
        membership = sell_membership(member, plan, today=date(2026, 1, 1))

    client = _client_for(owner, gym)
    response = client.post(f"/api/v1/invoices/{membership.invoice_id}/void/", {}, format="json")

    assert response.status_code == 400


def test_front_desk_cannot_void_an_invoice(owner_setup):
    _org, gym, _owner, front_desk, plan, member = owner_setup
    with system_context():
        membership = sell_membership(member, plan, today=date(2026, 1, 1))

    client = _client_for(front_desk, gym)
    response = client.post(
        f"/api/v1/invoices/{membership.invoice_id}/void/", {"reason": "x"}, format="json"
    )

    assert response.status_code == 403


def test_member_renewal_plans_lists_the_members_own_gym_plans(owner_setup):
    """Not token-driven through the usual _client_for helper — this whole
    family (plans/renew/callback) is unauthenticated, the signed pass
    token is the proof, same as MemberPassView.
    """
    from django.core import signing

    org, gym, _owner, _front_desk, plan, member = owner_setup
    token = signing.dumps({"member_id": member.pk}, salt="attendance.member-pass")

    client = APIClient()
    response = client.get(f"/api/v1/m/pass/{token}/plans")

    assert response.status_code == 200, response.content
    body = response.json()
    assert len(body) == 1
    assert body[0]["id"] == plan.pk
    assert body[0]["price_npr"] == "3000.00"


def test_member_renewal_addons_lists_the_members_own_gym_addons(owner_setup):
    from django.core import signing

    org, gym, _owner, _front_desk, _plan, member = owner_setup
    with system_context():
        addon = AddOn.objects.create(
            org=org, gym=gym, name="Locker", price_npr=Decimal("200.00"), kind=AddOn.Kind.LOCKER
        )
    token = signing.dumps({"member_id": member.pk}, salt="attendance.member-pass")

    client = APIClient()
    response = client.get(f"/api/v1/m/pass/{token}/addons")

    assert response.status_code == 200, response.content
    body = response.json()
    assert len(body) == 1
    assert body[0]["id"] == addon.pk
    assert body[0]["price_npr"] == "200.00"


def test_member_renewal_initiate_rejects_invalid_promo_code(owner_setup):
    from django.core import signing

    _org, gym, _owner, _front_desk, plan, member = owner_setup
    with system_context():
        GatewayCredential.objects.create(
            org=gym.org,
            gym=gym,
            provider=GatewayCredential.Provider.ESEWA,
            environment=GatewayCredential.Environment.SANDBOX,
            merchant_code="EPAYTEST",
            secret_encrypted=encrypt_bytes(b"8gBm/:&EnhH.1/q"),
        )
    token = signing.dumps({"member_id": member.pk}, salt="attendance.member-pass")

    client = APIClient()
    response = client.post(
        f"/api/v1/m/pass/{token}/renew",
        {
            "plan_id": plan.pk,
            "provider": "esewa",
            "return_url": "https://m.fitkhata.test/renew/return",
            "promo_code": "NOPE",
        },
        format="json",
    )

    assert response.status_code == 400
    assert "promo code" in response.json()["detail"].lower()


def test_member_renewal_initiate_applies_promo_and_addon_to_the_payment_amount(owner_setup):
    """plan 3000 - 10% promo (300) + 200 addon = 2900, and the resulting
    eSewa redirect form is signed for that discounted total, not the raw
    plan price — proving the view actually threads promo_code/addon_ids
    through to initiate_renewal_payment rather than ignoring them.
    """
    from django.core import signing

    org, gym, _owner, _front_desk, plan, member = owner_setup
    with system_context():
        GatewayCredential.objects.create(
            org=gym.org,
            gym=gym,
            provider=GatewayCredential.Provider.ESEWA,
            environment=GatewayCredential.Environment.SANDBOX,
            merchant_code="EPAYTEST",
            secret_encrypted=encrypt_bytes(b"8gBm/:&EnhH.1/q"),
        )
        addon = AddOn.objects.create(
            org=org, gym=gym, name="Locker", price_npr=Decimal("200.00"), kind=AddOn.Kind.LOCKER
        )
        promo = PromoCode.objects.create(
            org=org,
            gym=gym,
            code="TENOFF",
            kind=PromoCode.Kind.PERCENT,
            value=Decimal("10"),
            valid_from=date(2020, 1, 1),
            valid_to=date(2099, 1, 1),
        )
    token = signing.dumps({"member_id": member.pk}, salt="attendance.member-pass")

    client = APIClient()
    response = client.post(
        f"/api/v1/m/pass/{token}/renew",
        {
            "plan_id": plan.pk,
            "provider": "esewa",
            "return_url": "https://m.fitkhata.test/renew/return",
            "promo_code": promo.code,
            "addon_ids": [addon.pk],
        },
        format="json",
    )

    assert response.status_code == 200, response.content
    body = response.json()
    assert body["redirect"]["fields"]["total_amount"] == "2900.00"
    with system_context():
        payment = Payment.objects.get(pk=body["payment_id"])
    assert payment.amount_npr == Decimal("2900.00")
    assert payment.metadata["addon_ids"] == [addon.pk]


def test_member_renewal_initiate_allows_fonepay_as_a_provider(owner_setup):
    """Fonepay has no credential configured for this gym in this test —
    the point is only that it reaches the gateway (GatewayNotConfigured)
    instead of being rejected upfront as an unsupported provider.
    """
    from django.core import signing

    _org, gym, _owner, _front_desk, plan, member = owner_setup
    token = signing.dumps({"member_id": member.pk}, salt="attendance.member-pass")

    client = APIClient()
    response = client.post(
        f"/api/v1/m/pass/{token}/renew",
        {
            "plan_id": plan.pk,
            "provider": "fonepay",
            "return_url": "",
        },
        format="json",
    )

    assert response.status_code == 400
    assert "fonepay" in response.json()["detail"].lower()
    assert "unsupported provider" not in response.json()["detail"].lower()


def test_member_renewal_callback_polls_fonepay_status_until_completed(owner_setup):
    """Fonepay never redirects back — the PWA polls this same callback
    endpoint while the member is scanning the QR. Confirms the callback
    view's Fonepay branch builds the {"prn", "gym"} verify() payload
    FonepayGateway expects, rather than falling into "unsupported".
    """
    org, gym, _owner, _front_desk, _plan, member = owner_setup
    with system_context():
        GatewayCredential.objects.create(
            org=gym.org,
            gym=gym,
            provider=GatewayCredential.Provider.FONEPAY,
            environment=GatewayCredential.Environment.SANDBOX,
            merchant_code="FONEPAY-MERCHANT",
            extra={"username": "fonepay-user"},
            secret_encrypted=encrypt_bytes(
                json.dumps({"password": "pw", "hmac_key": "hmac-key"}).encode("utf-8")
            ),
        )
        payment = Payment.objects.create(
            org=org,
            gym=gym,
            member=member,
            mode=Payment.Mode.FONEPAY,
            channel=Payment.Channel.ONLINE,
            transaction_uuid=uuid.uuid4(),
            amount_npr=Decimal("3000.00"),
            status=Payment.Status.PENDING,
            metadata={"renewal": True, "plan_id": 1, "promo_code": None, "addon_ids": []},
        )

    mock_response = Mock()
    mock_response.json.return_value = {"paymentStatus": "pending"}
    mock_response.raise_for_status.return_value = None

    client = APIClient()
    with patch("billing.gateways.fonepay.requests.post", return_value=mock_response):
        pending = client.post(
            "/api/v1/billing/renewals/callback",
            {"provider": "fonepay", "payment_id": payment.pk},
            format="json",
        )
    assert pending.status_code == 200, pending.content
    assert pending.json() == {"status": "pending"}

    mock_response.json.return_value = {
        "paymentStatus": "success",
        "fonepayTraceId": "trace-1",
    }
    with system_context():
        plan = Plan.objects.create(
            org=org, gym=gym, name="Monthly", duration_days=30, price_npr=Decimal("3000.00")
        )
        payment.metadata["plan_id"] = plan.pk
        payment.save(update_fields=["metadata"])
    with patch("billing.gateways.fonepay.requests.post", return_value=mock_response):
        completed = client.post(
            "/api/v1/billing/renewals/callback",
            {"provider": "fonepay", "payment_id": payment.pk},
            format="json",
        )

    assert completed.status_code == 200, completed.content
    assert completed.json() == {"status": "completed"}
    with system_context():
        payment.refresh_from_db()
    assert payment.status == Payment.Status.COMPLETED


def test_owner_can_read_org_settings(owner_setup):
    _org, gym, owner, _front_desk, _plan, _member = owner_setup
    client = _client_for(owner, gym)

    response = client.get("/api/v1/orgs/settings")

    assert response.status_code == 200, response.content
    assert "vat_inclusive_pricing" in response.json()


def test_front_desk_cannot_update_org_settings(owner_setup):
    _org, gym, _owner, front_desk, _plan, _member = owner_setup
    client = _client_for(front_desk, gym)

    response = client.patch(
        "/api/v1/orgs/settings", {"vat_inclusive_pricing": True}, format="json"
    )

    assert response.status_code == 403
