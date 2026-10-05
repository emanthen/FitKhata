#!/usr/bin/env bash
set -euo pipefail

log() { echo "[backup] $(date -u +%FT%TZ) $*"; }

log "starting wal-g base backup"
wal-g backup-push "$PGDATA"
log "base backup done"

/scripts/retention-prune.sh

log "nightly backup cycle complete"
