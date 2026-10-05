-- Rule 2b/3: the app connects as a non-superuser, non-BYPASSRLS role so RLS
-- policies actually apply to it. A separate BYPASSRLS role exists only for
-- system/cross-tenant jobs (core.context.system_context).
-- CREATEDB is only so this role can create the pytest-django test database;
-- it's orthogonal to BYPASSRLS, so RLS still applies to everything it owns.
CREATE ROLE fitkhata_app LOGIN PASSWORD 'fitkhata_app' NOSUPERUSER NOBYPASSRLS CREATEDB;
CREATE ROLE fitkhata_system LOGIN PASSWORD 'fitkhata_system' NOSUPERUSER BYPASSRLS;

ALTER DATABASE fitkhata OWNER TO fitkhata_app;
GRANT ALL PRIVILEGES ON DATABASE fitkhata TO fitkhata_app, fitkhata_system;

-- Lets fitkhata_app do `SET LOCAL ROLE fitkhata_system` inside
-- core.context.system_context() — see that function's docstring. (The
-- reverse grant, fitkhata_system table access on fitkhata_app-owned
-- objects, can't also be a role-membership grant — Postgres rejects
-- circular membership — so it's handled per-database instead, by
-- core/migrations/0003_system_role_grants.py, which re-applies correctly
-- to pytest-django's ephemeral test database too.)
GRANT fitkhata_system TO fitkhata_app;
