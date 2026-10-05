#!/usr/bin/env bash
# Tests disaster recovery: fetches a WAL-G backup into a throwaway Postgres
# container, replays WAL, and verifies it comes up cleanly — all in a scratch
# volume. Never touches the running `postgres` service or its volume.
#
# Usage: restore.sh [BACKUP_NAME]   (defaults to LATEST)
#
# Requires in the environment: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY,
# AWS_ENDPOINT, WALG_S3_PREFIX (same values as the `postgres`/`backup`
# services use — see .env.prod).
set -euo pipefail

BACKUP_NAME="${1:-LATEST}"
IMAGE="${POSTGRES_IMAGE:-fitkhata-postgres:latest}"
SCRATCH_VOLUME="fitkhata_restore_scratch"
CONTAINER="fitkhata-restore-scratch"

log() { echo "[restore] $*"; }

for v in AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_ENDPOINT WALG_S3_PREFIX; do
  if [[ -z "${!v:-}" ]]; then
    echo "restore.sh: $v must be set in the environment" >&2
    exit 1
  fi
done

cleanup() {
  docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
}
trap cleanup EXIT

log "resetting scratch volume $SCRATCH_VOLUME"
docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
docker volume rm -f "$SCRATCH_VOLUME" >/dev/null 2>&1 || true
docker volume create "$SCRATCH_VOLUME" >/dev/null

walg_env=(-e AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY -e AWS_ENDPOINT -e AWS_S3_FORCE_PATH_STYLE=true -e WALG_S3_PREFIX)

log "fetching backup '$BACKUP_NAME' via wal-g backup-fetch"
docker run --rm "${walg_env[@]}" \
  -v "$SCRATCH_VOLUME:/var/lib/postgresql/data" \
  "$IMAGE" wal-g backup-fetch /var/lib/postgresql/data "$BACKUP_NAME"

log "writing recovery.signal + restore_command for WAL replay"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
docker run --rm \
  -v "$SCRATCH_VOLUME:/var/lib/postgresql/data" \
  -v "$SCRIPT_DIR/lib/prepare-recovery.sh:/prepare-recovery.sh:ro" \
  --entrypoint bash \
  "$IMAGE" /prepare-recovery.sh

log "starting scratch Postgres to replay WAL"
docker run -d --name "$CONTAINER" "${walg_env[@]}" \
  -e POSTGRES_PASSWORD=restore-drill-only \
  -v "$SCRATCH_VOLUME:/var/lib/postgresql/data" \
  "$IMAGE" >/dev/null

log "waiting for recovery to finish and the server to accept connections..."
for i in $(seq 1 60); do
  if docker exec "$CONTAINER" pg_isready -U postgres >/dev/null 2>&1; then
    log "server is up after ${i}0s — querying to confirm data is readable"
    docker exec "$CONTAINER" psql -U postgres -d fitkhata -c \
      "select now() as restored_at, (select count(*) from pg_stat_user_tables) as table_count;"
    log "RESTORE DRILL PASSED — scratch container '$CONTAINER' and volume '$SCRATCH_VOLUME' are left running for inspection."
    log "Clean up with: docker rm -f $CONTAINER && docker volume rm $SCRATCH_VOLUME"
    trap - EXIT
    exit 0
  fi
  sleep 10
done

log "RESTORE DRILL FAILED: server never became ready within 10 minutes"
docker logs "$CONTAINER" --tail 100
exit 1
