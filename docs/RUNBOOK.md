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

## Add a gym's payment keys

Per-gym payment provider credentials are stored Fernet-encrypted in the
database (`FIELD_ENCRYPTION_KEY` in `infra/.env` is the encryption key for
*all* gyms — rotating it requires re-encrypting every stored credential, so
treat it like a master key).

```bash
docker compose exec api python manage.py shell -c "
from gyms.models import Gym
gym = Gym.objects.get(pk=GYM_ID)
gym.payment_provider_key = 'the-provider-secret'  # encrypted on save via the model's Fernet field
gym.save()
"
```

(Swap in the real management command once the billing app grows one —
`manage.py shell` is the stopgap until then.)
