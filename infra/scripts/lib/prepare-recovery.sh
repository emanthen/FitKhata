#!/usr/bin/env bash
# Bind-mounted into the scratch container by restore.sh and run there —
# kept as a real file instead of an inline `-c` string to avoid multi-layer
# shell-quoting of the restore_command's %f/%p placeholders.
set -euo pipefail

cat >>/var/lib/postgresql/data/postgresql.auto.conf <<'EOF'
restore_command = 'wal-g wal-fetch "%f" "%p"'
EOF

touch /var/lib/postgresql/data/recovery.signal
chown -R postgres:postgres /var/lib/postgresql/data
