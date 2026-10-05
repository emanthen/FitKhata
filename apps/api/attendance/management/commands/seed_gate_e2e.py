"""Test-fixture helper for apps/web/e2e/gate-offline-sync.spec.ts — not a
production seed. Mirrors core.management.commands.seed_demo's pattern
(idempotent get_or_create, system_context() for the pre-tenant-scoping
writes) but purpose-built for the gate: it also registers a GateDevice and
prints the raw values (device token, member's plaintext qr_secret) the
Playwright test needs and that the server itself never re-exposes after
the fact.

Two subcommands:
    seed                          -- create a fresh fixture, print its JSON
    count --member-code=<code>    -- print how many Attendance rows exist
                                      for that member (the spec's server-side
                                      assertion, same query shape as
                                      attendance/tests/test_services.py)
"""

from __future__ import annotations

import json
import os
import uuid

from django.core.management.base import BaseCommand, CommandParser

from attendance.models import Attendance
from attendance.services import register_gate_device
from core.context import system_context
from core.crypto import encrypt_bytes
from gyms.models import Gym, Organization
from members.models import Member

ORG_NAME = "E2E Gate Test Org"
GYM_CODE = "E2E1"


class Command(BaseCommand):
    help = "Seed (or count) fixtures for the gate offline-sync Playwright spec."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("action", choices=["seed", "count"])
        parser.add_argument("--member-code")

    def handle(self, *args, **options) -> None:
        if options["action"] == "seed":
            self._seed()
        else:
            self._count(options["member_code"])

    def _seed(self) -> None:
        # A fresh member_code (and device) every call, never reused — the
        # Playwright spec asserts an exact Attendance row count for this
        # member, which a shared/idempotent fixture would slowly
        # accumulate across repeated runs and break.
        suffix = uuid.uuid4().hex[:10]
        with system_context():
            org, _ = Organization.objects.get_or_create(name=ORG_NAME)
            gym, _ = Gym.objects.get_or_create(
                org=org, code=GYM_CODE, defaults={"name": "E2E Gate Test Gym"}
            )
            raw_secret = os.urandom(32)
            member = Member.objects.create(
                org=org,
                gym=gym,
                member_code=f"E2E1-{suffix}",
                full_name="E2E Test Member",
                phone=f"+97798{int(suffix, 16) % 10**8:08d}",
                qr_secret=encrypt_bytes(raw_secret),
                status=Member.Status.ACTIVE,
            )
            device, raw_token = register_gate_device(gym, f"e2e-kiosk-{suffix}")

        self.stdout.write(
            json.dumps(
                {
                    "gym_id": str(gym.pk),
                    "member_code": member.member_code,
                    "qr_secret_hex": raw_secret.hex(),
                    "device_id": device.pk,
                    "device_token": raw_token,
                }
            )
        )

    def _count(self, member_code: str) -> None:
        with system_context():
            count = Attendance.objects.filter(member__member_code=member_code).count()
        self.stdout.write(json.dumps({"count": count}))
