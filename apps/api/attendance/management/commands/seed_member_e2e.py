"""Test-fixture helper for the Member PWA Playwright specs (renew-sandbox,
QR-refresh, offline-plan-view) -- not a production seed. Mirrors
seed_gate_e2e's shape (fresh member/gym every call, system_context() for
the pre-tenant-scoping writes, prints the one-shot JSON a spec needs).

Subcommand:
    seed    -- create a fresh member + a signed pass token, print its JSON
"""

from __future__ import annotations

import json
import os
import uuid
from decimal import Decimal

from django.core import signing
from django.core.management.base import BaseCommand, CommandParser

from attendance.views import MEMBER_PASS_SALT
from billing.models import GatewayCredential
from coaching.models import ClientProfile, Exercise, WorkoutPlan
from core.context import system_context
from core.crypto import encrypt_bytes
from gyms.models import Gym, Organization
from members.models import Member, Plan

ORG_NAME = "E2E Member Test Org"
GYM_CODE = "E2E2"

# eSewa's own published, shared sandbox test credentials (not a secret to
# protect — every integrator uses the same ones; see billing/gateways/
# esewa.py's module docstring).
ESEWA_SANDBOX_PRODUCT_CODE = "EPAYTEST"
ESEWA_SANDBOX_SECRET = "8gBm/:&EnhH.1/q"


class Command(BaseCommand):
    help = "Seed a fixture for the Member PWA Playwright specs."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("action", choices=["seed"])

    def handle(self, *args, **options) -> None:
        suffix = uuid.uuid4().hex[:10]
        with system_context():
            org, _ = Organization.objects.get_or_create(name=ORG_NAME)
            gym, _ = Gym.objects.get_or_create(
                org=org, code=GYM_CODE, defaults={"name": "E2E Member Test Gym"}
            )
            raw_secret = os.urandom(32)
            member = Member.objects.create(
                org=org,
                gym=gym,
                member_code=f"E2E2-{suffix}",
                full_name="E2E Member",
                phone=f"+97798{int(suffix, 16) % 10**8:08d}",
                qr_secret=encrypt_bytes(raw_secret),
                status=Member.Status.ACTIVE,
            )
            token = signing.dumps({"member_id": member.pk}, salt=MEMBER_PASS_SALT)

            plan, _ = Plan.objects.get_or_create(
                org=org,
                gym=gym,
                name="E2E Monthly",
                defaults={"duration_days": 30, "price_npr": Decimal("1000.00")},
            )
            GatewayCredential.objects.get_or_create(
                org=org,
                gym=gym,
                provider=GatewayCredential.Provider.ESEWA,
                environment=GatewayCredential.Environment.SANDBOX,
                defaults={
                    "merchant_code": ESEWA_SANDBOX_PRODUCT_CODE,
                    "secret_encrypted": encrypt_bytes(ESEWA_SANDBOX_SECRET.encode("utf-8")),
                },
            )

            # A real assigned workout plan, for the offline-plan-view spec —
            # any one global Exercise row (seeded by coaching's own
            # migration) is fine, this isn't exercising exercise selection.
            exercise = Exercise.objects.first()
            workout_plan = WorkoutPlan.objects.create(
                org=org,
                gym=gym,
                name="E2E Full Body",
                split=WorkoutPlan.Split.FULL_BODY,
                days=(
                    [
                        {
                            "day": "mon",
                            "exercises": [
                                {
                                    "exercise_id": str(exercise.pk),
                                    "sets": 3,
                                    "reps": 10,
                                    "rest_s": 60,
                                }
                            ],
                        }
                    ]
                    if exercise
                    else []
                ),
            )
            ClientProfile.objects.create(
                org=org,
                gym=gym,
                member=member,
                primary_goal=ClientProfile.Goal.GENERAL_FITNESS,
                starting_weight_kg=Decimal("70.00"),
                target_weight_kg=Decimal("70.00"),
                workout_plan=workout_plan,
            )

        self.stdout.write(
            json.dumps(
                {
                    "gym_code": gym.code,
                    "member_id": member.pk,
                    "member_code": member.member_code,
                    "qr_secret_hex": raw_secret.hex(),
                    "token": token,
                    "plan_id": plan.pk,
                }
            )
        )
