#!/usr/bin/env bash
# Idempotent one-time VPS provisioning for Ubuntu 24.04. Run as root:
#
#   SSH_PUBLIC_KEY="ssh-ed25519 AAAA... you@laptop" ./provision.sh
#
# Safe to re-run — every step checks current state first. Each step is
# ordered so a failure partway through never leaves SSH unreachable: the
# public key is installed and verified *before* password auth is disabled.
set -euo pipefail

DEPLOY_USER="${DEPLOY_USER:-deploy}"
SSH_PORT="${SSH_PORT:-22}"
SSH_PUBLIC_KEY="${SSH_PUBLIC_KEY:-}"
SWAP_SIZE_GB="${SWAP_SIZE_GB:-2}"

log() { echo "[provision] $*"; }

if [[ $EUID -ne 0 ]]; then
  echo "Run as root (e.g. sudo -i)." >&2
  exit 1
fi

if [[ -z "$SSH_PUBLIC_KEY" ]]; then
  echo "SSH_PUBLIC_KEY is required (export it or pass inline) — refusing to" >&2
  echo "disable password auth without a key already in place." >&2
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive

log "apt update/upgrade"
apt-get update -qq
apt-get -y -qq upgrade

log "timezone -> UTC"
timedatectl set-timezone UTC

# --- deploy user + SSH key ------------------------------------------------
if ! id "$DEPLOY_USER" &>/dev/null; then
  log "creating user $DEPLOY_USER"
  # No sudo group: deploy only needs the docker group (added below) to run
  # `docker compose`. It has no password set, so sudo wouldn't work anyway —
  # admin tasks go through this script (as root), not through deploy.
  adduser --disabled-password --gecos "" "$DEPLOY_USER"
fi

DEPLOY_HOME="/home/$DEPLOY_USER"
install -d -m 700 -o "$DEPLOY_USER" -g "$DEPLOY_USER" "$DEPLOY_HOME/.ssh"
AUTH_KEYS="$DEPLOY_HOME/.ssh/authorized_keys"
touch "$AUTH_KEYS"
if ! grep -qxF "$SSH_PUBLIC_KEY" "$AUTH_KEYS"; then
  log "installing SSH public key for $DEPLOY_USER"
  echo "$SSH_PUBLIC_KEY" >>"$AUTH_KEYS"
fi
chmod 600 "$AUTH_KEYS"
chown -R "$DEPLOY_USER:$DEPLOY_USER" "$DEPLOY_HOME/.ssh"

if [[ ! -s "$AUTH_KEYS" ]]; then
  echo "authorized_keys is empty after install — aborting before touching sshd." >&2
  exit 1
fi

# --- sshd hardening (drop-in, never edit the shipped file in place) ------
SSHD_DROPIN="/etc/ssh/sshd_config.d/99-fitkhata.conf"
log "writing $SSHD_DROPIN (port $SSH_PORT, no root/password login)"
cat >"$SSHD_DROPIN" <<EOF
Port $SSH_PORT
PermitRootLogin no
PasswordAuthentication no
PubkeyAuthentication yes
KbdInteractiveAuthentication no
EOF
sshd -t
systemctl reload ssh

# --- firewall --------------------------------------------------------------
log "configuring ufw"
apt-get install -y -qq ufw
ufw default deny incoming
ufw default allow outgoing
ufw allow "$SSH_PORT"/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

# --- fail2ban ---------------------------------------------------------------
log "installing fail2ban"
apt-get install -y -qq fail2ban
cat >/etc/fail2ban/jail.d/sshd.local <<EOF
[sshd]
enabled = true
port = $SSH_PORT
backend = systemd
maxretry = 5
bantime = 1h
EOF
systemctl enable --now fail2ban
systemctl restart fail2ban

# --- unattended upgrades -----------------------------------------------------
log "enabling unattended-upgrades"
apt-get install -y -qq unattended-upgrades
dpkg-reconfigure -f noninteractive unattended-upgrades

# --- swap --------------------------------------------------------------------
if ! swapon --show | grep -q '/swapfile'; then
  log "creating ${SWAP_SIZE_GB}G swapfile"
  fallocate -l "${SWAP_SIZE_GB}G" /swapfile
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  grep -qxF '/swapfile none swap sw 0 0' /etc/fstab || echo '/swapfile none swap sw 0 0' >>/etc/fstab
  sysctl -w vm.swappiness=10
  grep -qxF 'vm.swappiness=10' /etc/sysctl.conf || echo 'vm.swappiness=10' >>/etc/sysctl.conf
else
  log "swapfile already present, skipping"
fi

# --- Docker Engine + compose plugin ------------------------------------------
if ! command -v docker &>/dev/null; then
  log "installing Docker Engine"
  apt-get install -y -qq ca-certificates curl gnupg
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  # shellcheck disable=SC1091
  . /etc/os-release
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $VERSION_CODENAME stable" \
    >/etc/apt/sources.list.d/docker.list
  apt-get update -qq
  apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
else
  log "docker already installed, skipping"
fi
usermod -aG docker "$DEPLOY_USER"

log "done."
if [[ "$SSH_PORT" != "22" ]]; then
  log "IMPORTANT: SSH now listens on port $SSH_PORT, not 22. Before closing"
  log "this session, open a NEW connection in another terminal to confirm:"
  log "  ssh -p $SSH_PORT $DEPLOY_USER@<this-host>"
fi
