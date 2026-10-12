"""Session-wide pytest-django setup. CLAUDE.md rule 2b.

A superuser or BYPASSRLS role sails through every RLS policy regardless
of whether it's correct, so a test suite connected as one could stay
green while a real tenant-isolation bug ships — which is exactly what
happened when .github/workflows/ci.yml once pointed DATABASE_URL at
Postgres's own bootstrap superuser instead of fitkhata_app. This fixture
makes that class of misconfiguration fail loudly instead of silently.
"""

from __future__ import annotations

import pytest
from django.db import connection


@pytest.fixture(scope="session", autouse=True)
def _forbid_superuser_or_bypassrls_connection(django_db_setup, django_db_blocker):
    with django_db_blocker.unblock():
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user"
            )
            rolsuper, rolbypassrls = cursor.fetchone()

    if rolsuper or rolbypassrls:
        flags = ", ".join(
            flag
            for flag, is_set in (("superuser", rolsuper), ("BYPASSRLS", rolbypassrls))
            if is_set
        )
        pytest.exit(
            f"Tests are connected to Postgres as a role with {flags} — RLS "
            "policies would pass trivially regardless of whether they're "
            "correct. Connect as fitkhata_app (see infra/initdb/001-app-roles.sql), "
            "not a superuser or fitkhata_system.",
            returncode=1,
        )
