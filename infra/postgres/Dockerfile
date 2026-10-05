# Postgres 16 + WAL-G, so archive_command can ship WAL straight to R2
# without a sidecar sharing the data directory.
FROM postgres:16

# amd64 only — the x86_64 VPS this stack targets (DigitalOcean/Hetzner/etc).
# Building for arm64 instead: swap the asset suffix below for aarch64 and re-pin its checksum.
ARG WALG_VERSION=v3.0.9
ARG WALG_SHA256=444ce216230c254edef803e098a59a1746806da3e0d55671d7b0f0082db14ef4
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && curl -fsSL --retry 3 --retry-delay 2 --retry-all-errors --connect-timeout 15 --max-time 120 -o /usr/local/bin/wal-g.tar.gz \
       "https://github.com/wal-g/wal-g/releases/download/${WALG_VERSION}/wal-g-pg-24.04-amd64.tar.gz" \
    && echo "${WALG_SHA256}  /usr/local/bin/wal-g.tar.gz" | sha256sum -c - \
    && tar -xzf /usr/local/bin/wal-g.tar.gz -C /usr/local/bin \
    && mv /usr/local/bin/wal-g-pg-24.04-amd64 /usr/local/bin/wal-g \
    && rm /usr/local/bin/wal-g.tar.gz \
    && chmod +x /usr/local/bin/wal-g \
    && apt-get purge -y curl \
    && rm -rf /var/lib/apt/lists/*

COPY postgresql.conf /etc/postgresql/postgresql.conf
COPY initdb/ /docker-entrypoint-initdb.d/
RUN chmod +x /docker-entrypoint-initdb.d/*.sh

CMD ["postgres", "-c", "config_file=/etc/postgresql/postgresql.conf"]
