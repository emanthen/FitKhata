# Runbook

Operational procedures for the FitKhata production stack (`infra/`).
Assumes `infra/.env` already exists on the server (copied from
`infra/.env.example` and filled in — see that file for every required secret).

## Deploy

Deploys run automatically from CI (`.github/workflows/deploy.yml`):

- Push to `main` → deploys to **staging** automatically.
- Push a tag `vX.Y.Z` → deploys to **production**, gated by a manual approval
  on the `production` GitHub Environment (configure required reviewers under
  repo Settings → Environments → production).

To deploy by hand (e.g. CI is down), SSH in as `deploy` and run:

```bash
cd /srv/fitkhata/infra          # or wherever DEPLOY_PATH points
set -a; source .env; set +a
export IMAGE_TAG=v1.2.3         # the tag/sha you're deploying
docker compose pull web api
docker compose build postgres backup
docker compose run --rm \
  -e DATABASE_URL="postgres://fitkhata_system:${FITKHATA_SYSTEM_PASSWORD}@postgres:5432/fitkhata" \
  api python manage.py migrate --noinput
docker compose up -d --remove-orphans
curl -fsS https://$DOMAIN_API/readyz
```

Migrations always run as `fitkhata_system` (BYPASSRLS) — never `fitkhata_app` —
since a migration must be able to alter any tenant's rows regardless of RLS.

## Rollback

Every deploy is identified by `IMAGE_TAG` (the git SHA for staging, the tag
for production) — GHCR keeps every image that's ever been pushed, so rolling
back is redeploying an older tag:

```bash
cd /srv/fitkhata/infra
set -a; source .env; set +a
export IMAGE_TAG=v1.2.2         # the last known-good tag
docker compose pull web api
docker compose up -d --remove-orphans
```

If the bad release included a migration that isn't safely reversible, don't
roll back the database automatically — restore from backup instead (below),
or write and apply a compensating migration. Never run `migrate` backwards
blind.

## Restore the database

**Test restores regularly** with `infra/scripts/restore.sh` — it never
touches the live `postgres` service, only a scratch container + scratch
volume, so it's safe to run anytime:

```bash
cd /srv/fitkhata/infra
set -a; source .env; set +a
export AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_ENDPOINT WALG_S3_PREFIX
export POSTGRES_IMAGE=$(docker compose config --format json | jq -r '.services.postgres.image // "fitkhata-infra-postgres"')
./scripts/restore.sh LATEST
```

That fetches the latest base backup + replays WAL, starts a throwaway
Postgres, and runs a sanity query. Leave it running to inspect data, or clean
up with the `docker rm`/`docker volume rm` commands it prints at the end.

**To actually restore production** (e.g. after data loss):

1. Put the app in maintenance mode (stop `api`, `worker`, `beat`, `channels`
   so nothing writes during the restore):
   ```bash
   docker compose stop api worker beat channels
   ```
2. Run `./scripts/restore.sh [BACKUP_NAME]` as above and confirm the data in
   the scratch container looks right.
3. Stop the real `postgres` service and swap its volume for the restored one:
   ```bash
   docker compose stop postgres
   docker volume rm fitkhata_pgdata
   docker run --rm -v fitkhata_restore_scratch:/from -v fitkhata_pgdata:/to alpine \
     sh -c "cp -a /from/. /to/"
   docker compose up -d postgres
   ```
4. Wait for `postgres` to report healthy, then bring the rest back up:
   ```bash
   docker compose up -d --remove-orphans
   ```
5. Clean up the scratch volume: `docker volume rm fitkhata_restore_scratch`.

Continuous WAL archiving means point-in-time recovery loses at most
`archive_timeout` (60s, see `infra/postgres/postgresql.conf`) plus whatever
WAL hadn't shipped yet — comfortably under the 5-minute acceptance target.

## Rotate secrets

Secrets live only in `infra/.env` on each server (never in git). To rotate
one:

1. **Django secret / Fernet key / Sentry DSN / R2 keys**: edit `infra/.env`,
   then `docker compose up -d --remove-orphans` to restart every service with
   the new value (R2 key rotation also needs the new key created on the
   Cloudflare R2 side first — create it before you deploy the swap, so there's
   no gap where the old key is revoked but the new one isn't live yet).
2. **`fitkhata_app` / `fitkhata_system` Postgres passwords**: these aren't
   re-read from `infra/.env` after first boot (the init script only runs
   once against a fresh data directory), so rotate with `ALTER ROLE`:
   ```bash
   docker compose exec postgres psql -U postgres -d fitkhata -c \
     "ALTER ROLE fitkhata_app WITH PASSWORD 'NEW_PASSWORD';"
   ```
   Then update `FITKHATA_APP_PASSWORD` in `infra/.env` and
   `docker compose up -d --remove-orphans` so the app picks it up. Same
   pattern for `fitkhata_system`.
3. **SSH deploy key**: generate a new keypair, add the new public key via
   `infra/scripts/provision.sh` (safe to re-run), confirm you can log in with
   it, then remove the old key from `~deploy/.ssh/authorized_keys` and from
   the `SSH_PRIVATE_KEY` GitHub secret.

## Tune worker counts for the VPS size

`GUNICORN_WORKERS` (set in `infra/.env`, read by `infra/docker-compose.yml`'s
`api` service) controls the API's gunicorn process count — H2's own rule of
thumb is `(2 x vCPU) + 1`:

| Server | vCPU | `GUNICORN_WORKERS` |
|---|---|---|
| `prod-1` | 4 | `9` |
| `staging-1` | 2 | `5` (the compose file's default — only prod needs the override) |

Before this was tuned, the API ran with gunicorn's bare default of **1**
worker (no `--workers` flag was ever set) — fine for `make dev`'s single-
request local testing, silently a bottleneck in anything resembling real
traffic. Check it's actually taking effect after a deploy:

```bash
docker compose exec api ps aux | grep -c "gunicorn: worker"
```

Celery's own worker concurrency isn't tuned here — it defaults to the
container's visible CPU count (`os.cpu_count()`), which is already correct
without an explicit flag.

**Not done yet, flagged not fixed:** connection pooling (PgBouncer, transaction
mode). At the stated scale (move Postgres to its own box around 300 gyms)
this isn't yet a bottleneck, but when it is: transaction-mode pooling is
required, not session-mode — `core.context.tenant_context`'s RLS scoping
uses `SET LOCAL app.gym_ids`, which only lives for the current transaction
and resets automatically before the connection returns to the pool. Session
mode would leak one request's `gym_ids` into the next request that happens
to grab the same pooled connection — a real cross-tenant data leak, not a
theoretical one. **Add `tests/rls/test_isolation.py` coverage running
through an actual PgBouncer instance before trusting this in production**,
not just the no-pooling path it tests today.

## Load testing

k6 scenarios for the traffic shapes that actually matter here (gate batch
sync, member search, owner dashboard, payment collection) live in
`tests/load/` — see `tests/load/README.md` for what each one needs seeded
on the target before it means anything. None of them have been run against
a live target as of this writing; they're new, not yet a passing gate.

## Add a gym's payment keys

This section was a placeholder written before `GatewayCredential` existed
and had gone stale (referenced a `Gym.payment_provider_key` field that was
never actually built) — corrected 2026-10-11.

Per-gym payment provider credentials are stored Fernet-encrypted in
`billing.models.GatewayCredential`, one row per (gym, provider,
environment) (`FIELD_ENCRYPTION_KEY` in `infra/.env` is the encryption key
for *every* gym's credentials — rotating it requires re-encrypting every
stored row, so treat it like a master key). Creation goes through
`GatewayCredentialSerializer.create()` (encryption happens there), called
via `GatewayCredentialViewSet` — there's no standalone service function to
script a one-off creation against. **Always use the web UI** (owner,
**Settings → Payment gateways & VAT**) rather than reaching for the Django
shell here — see "Go live on a pilot gym's real payment gateway" below for
the full sandbox→live sequence.

## Onboard a real pilot gym

H3's "seed scripts for a real gym" — this is the actual sequence, not a
script, since every step after the first needs that gym's own real data
(their member list, their real gateway merchant credentials) that no
seed script could provide. Follow `docs/onboarding/owner-guide.en.md` for
the UI walkthrough; this is the ops-side checklist and the two things
that need more care than the guide spells out: the Excel import format,
and the live-payment verification step.

1. **Organization + first branch + plans + staff invites** — the owner
   does this themselves via the 4-step onboarding wizard
   (`docs/onboarding/owner-guide.en.md` §1). Nothing ops-specific here.

2. **Import their existing members** (**Settings → Membership → Import
   members**, or `POST /api/v1/members/import` directly). The importer
   (`members/tasks.py::import_members_task`) accepts CSV or XLSX with
   these exact column headers — get the gym's spreadsheet into this shape
   before uploading, this is the #1 reason an import comes back with a
   long error report:

   | Column | Required | Format |
   |---|---|---|
   | `full_name` | yes | plain text |
   | `phone` | yes | any format accepted, but must be a real, unique number per member |
   | `gender` | no | free text, lowercased on import |
   | `dob` | no | `YYYY-MM-DD` — anything else fails that row |
   | `tags` | no | comma-separated, e.g. `vip,referral` |
   | `marketing_opt_in` | no | `true`/`1`/`yes` for opted in, anything else (including blank) is opted out |

   A row missing `full_name` or `phone`, or with a malformed `dob`, fails
   just that row — the job still completes, and `ImportJob.error_report`
   (downloadable from the import screen) lists exactly which rows and
   why, so the gym can fix and re-upload only those rows rather than the
   whole file. Memberships/plans/payment history don't come across in
   this importer — it's members-only (FR-2.8's own scope); if the pilot
   gym needs their active memberships recreated too, that's a manual
   follow-up per member, not something to script around this importer.

3. **Go live on the gym's real payment gateway.** Do not skip the test
   transaction — `test_connection` (the "Test connection" button next to
   each credential) is explicitly **not** a full credential check for
   eSewa (its own docstring: "a success... just means the request was
   well-formed" — eSewa has no dedicated credential-validation endpoint
   short of an actual payment attempt). For Khalti it does catch a wrong
   secret key outright; for eSewa and Fonepay it doesn't.

   1. Add the gym's real merchant credential in **sandbox** mode first.
      Run a test renewal through the Member PWA against the sandbox
      credential, confirm it completes and the membership activates.
   2. Switch the same credential's environment to **live** (owner-only,
      same settings page) with the gym's real merchant credentials.
   3. **Run one real NPR 10 transaction** through the actual desk-collect
      or member-renewal flow — not `test_connection`, a real payment a
      real person completes — and confirm: the payment shows completed,
      the invoice issues, and the money actually lands in the gym's own
      merchant account (check their eSewa/Khalti/Fonepay merchant
      dashboard directly, not just FitKhata's side). Only once all three
      are confirmed is this gym's live gateway trustworthy for their real
      members' money.
      For eSewa specifically: this is also the only way to get a genuine
      sandbox/live callback `data` payload to add as a permanent test
      fixture — `billing/gateways/esewa.py`'s response-signature check
      (fixed in `fix/pilot-blockers`) was built to read eSewa's own
      `signed_field_names` rather than assume a fixed field list, but it's
      never been verified against an actual eSewa response from this
      environment (no live network access here). Capture that NPR 10
      transaction's raw callback JSON (minus the real signature's secret
      inputs) and add it to `billing/gateways/tests/test_esewa.py` the
      first time this step runs for real.
   4. Refund or keep the NPR 10 per the gym's own preference — FitKhata
      has no automatic refund path for this, it's between the gym and
      whoever made the test payment.

(Swap in the real management command once the billing app grows one —
`manage.py shell` is the stopgap until then.)
