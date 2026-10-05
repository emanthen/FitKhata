# FitKhata — Project Memory

## Product
Multi-tenant gym management SaaS for Nepal. Requirements: docs/SRS.md (v5.0).
Cite FR/NFR IDs in commits and PRs. If SRS mentions Supabase/Vercel, this file wins.

## Stack (fixed, self-hosted on VPS)
Monorepo:
- apps/api: Python 3.12, Django 5.1, Django REST Framework, drf-spectacular (OpenAPI), SimpleJWT
- apps/api workers: Celery 5 + Celery Beat (Redis broker), Django Channels (Redis) for realtime
- apps/web: Next.js 15 App Router, TypeScript strict, Tailwind, shadcn/ui, next-intl (ne, en), TanStack Query, Dexie (IndexedDB), Workbox PWA; output: 'standalone'
- apps/bridge: Node.js 20 service for ZKTeco + ESC/POS printers
- packages/api-client: TS client generated from the OpenAPI schema (orval)
- infra/: docker-compose.yml (prod), docker-compose.dev.yml, Caddyfile, backup scripts
- Data: PostgreSQL 16 (RLS on), Redis 7, Cloudflare R2 (S3 API) for files — MinIO's open-source edition was archived upstream in 2026 (no more images/mc releases), so prod writes directly to R2 via django-storages; no local object-store service
- Tests: pytest + pytest-django + factory_boy (api), Vitest (web), Playwright (E2E)
- Tooling: uv (Python deps), ruff + mypy, pnpm, Makefile at root

## Architecture rules (non-negotiable)
1. Shared schema multi-tenancy. Every tenant model inherits TenantModel (org FK, gym FK, created_at, updated_at).
2. Two layers of isolation: (a) TenantQuerySet + DRF permission scope every query by request.gym; (b) Postgres RLS policies on every tenant table using current_setting('app.gym_ids') set per request by middleware in a transaction (SET LOCAL). The app DB role is NOT a superuser and does NOT bypass RLS.
3. Celery tasks and management commands run under an explicit tenant context helper: with tenant_context(gym_ids=[...]) or system_context() for cross-tenant jobs (separate DB role with BYPASSRLS, used only there).
4. Money: DecimalField(max_digits=12, decimal_places=2), NPR. Never float. Display with lakh grouping (1,00,000).
5. Time: USE_TZ=True, store UTC, display Asia/Kathmandu (+05:45). Show BS + AD dates.
6. Payment confirmation is server-side only and idempotent on transaction_uuid (unique constraint + select_for_update).
7. Payments, invoices, cash shifts are never edited in place: service functions only, each writes AuditLog.
8. Invoice numbers: sequential per org per fiscal year (Shrawan–Asar), gapless (row lock on a counter table), void instead of delete.
9. Business logic lives in apps/api/<app>/services.py and domain/ (pure functions, unit-tested). Views stay thin.
10. Secrets only in env files on the server (never committed); payment keys per gym encrypted in DB with Fernet (key from env).
11. All UI text via next-intl; add ne and en keys together.
12. QR token algorithm is implemented in Python (api) and TypeScript (web) and must pass the same test vectors in shared/qr_vectors.json.

## Workflow
- Plan first; wait for approval on large changes.
- One Django migration per change; never edit applied migrations. RLS policies go in RunSQL migrations.
- After API changes: make schema (regenerates OpenAPI + packages/api-client).
- Before finishing: make lint && make test

## Commands
- make dev — docker compose dev (postgres, redis, minio for local-only dev storage, api, worker, web)
- make test — pytest + vitest; make test-rls — RLS isolation suite; make e2e — Playwright
- make migrate / make seed / make schema
- make deploy-staging — (CI only) pull images on staging VPS and restart