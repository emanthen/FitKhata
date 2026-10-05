#!/usr/bin/env bash
# Runs a Postgres base backup + retention prune once a day at BACKUP_HOUR_UTC.
# No cron daemon — just a sleep loop, since there's exactly one job to run.
set -euo pipefail

log() { echo "[backup] $(date -u +%FT%TZ) $*"; }

BACKUP_HOUR_UTC="${BACKUP_HOUR_UTC:-2}"

seconds_until_next_run() {
  local hour minute second since_midnight target_offset
  hour=$(date -u +%H); minute=$(date -u +%M); second=$(date -u +%S)
  since_midnight=$((10#$hour * 3600 + 10#$minute * 60 + 10#$second))
  target_offset=$((10#$BACKUP_HOUR_UTC * 3600))
  if ((since_midnight < target_offset)); then
    echo $((target_offset - since_midnight))
  else
    echo $((86400 - since_midnight + target_offset))
  fi
}

log "backup sidecar started; nightly run at ${BACKUP_HOUR_UTC}:00 UTC"
while true; do
  wait_s=$(seconds_until_next_run)
  log "sleeping ${wait_s}s until next run"
  sleep "$wait_s"
  /scripts/run-backup.sh || log "run-backup.sh failed — see above; will retry next cycle"
done
