#!/usr/bin/env bash
# Runs once, only against a brand-new data directory (standard
# docker-entrypoint-initdb.d behavior) — never re-applied to an existing DB,
# so rotating these passwords later needs ALTER ROLE, not a re-run of this
# script (see docs/RUNBOOK.md).
set -euo pipefail

: "${FITKHATA_APP_PASSWORD:?FITKHATA_APP_PASSWORD must be set}"
: "${FITKHATA_SYSTEM_PASSWORD:?FITKHATA_SYSTEM_PASSWORD must be set}"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -v app_pw="$FITKHATA_APP_PASSWORD" \
  -v sys_pw="$FITKHATA_SYSTEM_PASSWORD" <<'SQL'
-- CLAUDE.md rule 2b/3: the app connects as a non-superuser, non-BYPASSRLS
-- role. fitkhata_system is for Celery system_context() jobs and migrations,
-- and doubles as the backup role (REPLICATION, for wal-g base backups).
CREATE ROLE fitkhata_app LOGIN PASSWORD :'app_pw' NOSUPERUSER NOBYPASSRLS;
CREATE ROLE fitkhata_system LOGIN PASSWORD :'sys_pw' NOSUPERUSER BYPASSRLS REPLICATION;

ALTER DATABASE fitkhata OWNER TO fitkhata_system;
GRANT ALL PRIVILEGES ON DATABASE fitkhata TO fitkhata_app, fitkhata_system;
GRANT USAGE ON SCHEMA public TO fitkhata_app;

-- Lets fitkhata_app do `SET LOCAL ROLE fitkhata_system` inside
-- core.context.system_context() — see that function's docstring.
GRANT fitkhata_system TO fitkhata_app;

-- Database-level GRANT above doesn't cover tables — every table/sequence
-- migrations create will be owned by fitkhata_system, so without this
-- fitkhata_app couldn't read or write a single row despite CLAUDE.md rule 2b
-- expecting it to be the app's normal runtime role.
ALTER DEFAULT PRIVILEGES FOR ROLE fitkhata_system IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO fitkhata_app;
ALTER DEFAULT PRIVILEGES FOR ROLE fitkhata_system IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO fitkhata_app;

CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
SQL
