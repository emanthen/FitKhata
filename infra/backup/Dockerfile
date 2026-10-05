# Nightly Postgres base-backup + retention sidecar.
# Debian-based (not Alpine) because wal-g's official release binaries are
# glibc-linked and don't run on musl. amd64 only — the x86_64 VPS this stack
# targets; for arm64 swap the wal-g asset suffix for aarch64 and re-pin its checksum.
FROM debian:bookworm-slim

ARG WALG_VERSION=v3.0.9
ARG WALG_SHA256=444ce216230c254edef803e098a59a1746806da3e0d55671d7b0f0082db14ef4
# postgresql-client-15 is only used for psql/pg_isready sanity checks, which
# are protocol-compatible with the v16 server — exact version parity isn't needed.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl bash jq postgresql-client-15 \
    && curl -fsSL --retry 3 --retry-delay 2 --retry-all-errors --connect-timeout 15 --max-time 120 -o /tmp/wal-g.tar.gz \
       "https://github.com/wal-g/wal-g/releases/download/${WALG_VERSION}/wal-g-pg-24.04-amd64.tar.gz" \
    && echo "${WALG_SHA256}  /tmp/wal-g.tar.gz" | sha256sum -c - \
    && tar -xzf /tmp/wal-g.tar.gz -C /usr/local/bin \
    && mv /usr/local/bin/wal-g-pg-24.04-amd64 /usr/local/bin/wal-g \
    && chmod +x /usr/local/bin/wal-g \
    && rm /tmp/wal-g.tar.gz \
    && apt-get purge -y curl \
    && rm -rf /var/lib/apt/lists/*

COPY scripts/ /scripts/
RUN chmod +x /scripts/*.sh

ENTRYPOINT ["/scripts/entrypoint.sh"]
