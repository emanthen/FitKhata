#!/usr/bin/env bash
# Keeps every backup from the last 7 days, plus the oldest backup of each of
# the last 4 distinct ISO weeks before that; deletes everything else.
set -euo pipefail

log() { echo "[backup] $(date -u +%FT%TZ) $*"; }

now_epoch=$(date -u +%s)

plan=$(wal-g backup-list --json | jq --argjson now_epoch "$now_epoch" '
  map({name: .backup_name, t: (.time | strptime("%Y-%m-%dT%H:%M:%SZ") | mktime)}) as $all
  | (def week_key: gmtime | strftime("%G-%V");
     ($all | map(select(($now_epoch - .t) <= 7*86400))) as $recent
     | ($all | map(select(($now_epoch - .t) > 7*86400))) as $old
     | ($old | group_by(.t | week_key) | map(.[0])) as $weekly_candidates
     | ($weekly_candidates | sort_by(.t) | reverse | .[0:4]) as $weekly_keep
     | ($recent + $weekly_keep) as $keep
     | ($all - $keep) as $delete
     | {keep: ($keep | map(.name)), delete: ($delete | map(.name))}
    )
')

keep_count=$(jq -r '.keep | length' <<<"$plan")
delete_count=$(jq -r '.delete | length' <<<"$plan")
log "retention: keeping $keep_count backup(s), deleting $delete_count"

jq -r '.delete[]' <<<"$plan" | while read -r name; do
  [[ -z "$name" ]] && continue
  log "deleting backup $name"
  wal-g delete target "$name" --confirm
done
