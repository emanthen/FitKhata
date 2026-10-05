"""Grants fitkhata_system table/sequence access on whatever role actually
ran the migrations that created them.

In prod that's fitkhata_system itself (a harmless no-op grant to itself). In
dev it's fitkhata_app, which owns every table — and since Postgres rejects
circular role membership, the SET ROLE capability granted the other way
(infra/initdb's `GRANT fitkhata_system TO fitkhata_app`) can't be mirrored as
a plain role-membership grant back. Using current_user makes this one
migration correct in both environments, and — critically — it reapplies to
pytest-django's freshly-created ephemeral test database on every test run,
unlike an infra-level init script (ALTER DEFAULT PRIVILEGES is stored
per-database, so a grant made once against the main `fitkhata` database
would never reach `test_fitkhata`).
"""

from django.db import migrations

GRANT_SQL = """
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'fitkhata_system') THEN
        EXECUTE format(
            'ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA public '
            'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO fitkhata_system',
            current_user
        );
        EXECUTE format(
            'ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA public '
            'GRANT USAGE, SELECT ON SEQUENCES TO fitkhata_system',
            current_user
        );
        GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO fitkhata_system;
        GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO fitkhata_system;
    END IF;
END
$$;
"""

REVOKE_SQL = """
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'fitkhata_system') THEN
        REVOKE ALL ON ALL TABLES IN SCHEMA public FROM fitkhata_system;
        REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM fitkhata_system;
        EXECUTE format(
            'ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA public '
            'REVOKE ALL ON TABLES FROM fitkhata_system',
            current_user
        );
        EXECUTE format(
            'ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA public '
            'REVOKE ALL ON SEQUENCES FROM fitkhata_system',
            current_user
        );
    END IF;
END
$$;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0002_rls"),
    ]

    operations = [
        migrations.RunSQL(sql=GRANT_SQL, reverse_sql=REVOKE_SQL),
    ]
