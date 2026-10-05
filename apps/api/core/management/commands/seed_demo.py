from __future__ import annotations

import os
import random
from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand

from accounts.models import StaffRole, User
from core.context import system_context
from core.crypto import encrypt_bytes
from gyms.models import Gym, Organization
from members.models import AddOn, Member, Plan

FIRST_NAMES = [
    "Ram", "Sita", "Hari", "Gita", "Shyam", "Radha", "Suresh", "Anita",
    "Prakash", "Sunita", "Bishnu", "Kamala", "Dipak", "Sarita", "Rajesh",
    "Sabina", "Niraj", "Puja", "Kiran", "Laxmi",
]
LAST_NAMES = [
    "Shrestha", "Gurung", "Thapa", "Rai", "Magar", "Tamang", "Lama",
    "Bastola", "Khadka", "Adhikari", "Karki", "Poudel", "Basnet", "Acharya",
]


def _phone(rng: random.Random) -> str:
    # Nepali mobile numbers: 98XXXXXXXX (10 digits) — E.164 for storage per
    # accounts.models.phone_validator.
    return f"+97798{rng.randint(0, 99999999):08d}"


class Command(BaseCommand):
    help = "Seed demo + benchmark data: 2 orgs, 3 gyms, 10,000 members (FR-2 acceptance)."

    def handle(self, *args, **options) -> None:
        # Seeding spans tenants that don't exist yet, same bootstrapping
        # problem as onboarding (gyms.views) and TenantMiddleware's own gym
        # resolution — see core.context.system_context.
        with system_context():
            org1, gym1, gym2 = self._seed_org_demo_fitness()
            org2, gym3 = self._seed_org_second()
            self._seed_plans_and_addons([gym1, gym2, gym3])
            self._seed_members([gym1, gym2, gym3])
            member_count = Member.objects.filter(gym__in=[gym1, gym2, gym3]).count()

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded orgs=[{org1}, {org2}] gyms=[{gym1}, {gym2}, {gym3}] "
                f"members={member_count}"
            )
        )

    def _seed_org_demo_fitness(self) -> tuple[Organization, Gym, Gym]:
        org, _ = Organization.objects.get_or_create(name="Demo Fitness")
        gym1, _ = Gym.objects.get_or_create(
            org=org, code="DEMO-KTM", defaults={"name": "Demo Fitness - Kathmandu"}
        )
        gym2, _ = Gym.objects.get_or_create(
            org=org, code="DEMO-PKR", defaults={"name": "Demo Fitness - Pokhara"}
        )
        user, created = User.objects.get_or_create(
            phone="+9779800000000",
            defaults={"full_name": "Demo Owner", "email": "owner@demo.fitkhata.local"},
        )
        if created:
            user.set_password("demopass123")
            user.save()
        StaffRole.objects.get_or_create(user=user, org=org, gym=None, role=StaffRole.Role.OWNER)
        return org, gym1, gym2

    def _seed_org_second(self) -> tuple[Organization, Gym]:
        org, _ = Organization.objects.get_or_create(name="Himalayan Fitness Club")
        gym, _ = Gym.objects.get_or_create(
            org=org, code="HFC-BKT", defaults={"name": "Himalayan Fitness - Bhaktapur"}
        )
        return org, gym

    def _seed_plans_and_addons(self, gyms: list[Gym]) -> None:
        for gym in gyms:
            Plan.objects.get_or_create(
                org=gym.org,
                gym=gym,
                name="Monthly",
                defaults={"duration_days": 30, "price_npr": Decimal("2500.00")},
            )
            Plan.objects.get_or_create(
                org=gym.org,
                gym=gym,
                name="Quarterly",
                defaults={"duration_days": 90, "price_npr": Decimal("6500.00")},
            )
            Plan.objects.get_or_create(
                org=gym.org,
                gym=gym,
                name="Annual",
                defaults={"duration_days": 365, "price_npr": Decimal("22000.00")},
            )
            AddOn.objects.get_or_create(
                org=gym.org,
                gym=gym,
                name="Locker",
                defaults={"price_npr": Decimal("300.00"), "kind": AddOn.Kind.LOCKER},
            )
            AddOn.objects.get_or_create(
                org=gym.org,
                gym=gym,
                name="Personal Training (4 sessions)",
                defaults={"price_npr": Decimal("4000.00"), "kind": AddOn.Kind.PT},
            )

    def _seed_members(self, gyms: list[Gym], total: int = 10_000) -> None:
        if Member.objects.filter(gym__in=gyms).count() >= total:
            self.stdout.write("Members already seeded, skipping.")
            return

        rng = random.Random(42)
        per_gym = total // len(gyms)
        members = []
        for gym in gyms:
            for i in range(per_gym):
                full_name = f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"
                members.append(
                    Member(
                        org=gym.org,
                        gym=gym,
                        member_code=f"{gym.code}-{i + 1:05d}",
                        full_name=full_name,
                        phone=_phone(rng),
                        dob=date(rng.randint(1970, 2008), rng.randint(1, 12), rng.randint(1, 28)),
                        # Fernet-encrypted at rest (members.Member.qr_secret's own
                        # contract — core.crypto, rule 10) — GateSnapshotView's
                        # decrypt_bytes() would raise InvalidToken on raw bytes.
                        qr_secret=encrypt_bytes(os.urandom(32)),
                    )
                )
        Member.objects.bulk_create(members, batch_size=1000, ignore_conflicts=True)
