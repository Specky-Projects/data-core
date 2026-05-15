#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root or with sudo."
  exit 1
fi

apt update
apt upgrade -y
apt install -y curl git ufw fail2ban ca-certificates
timedatectl set-timezone "${TZ:-America/Sao_Paulo}"

ufw default deny incoming
ufw default allow outgoing
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

echo "Base server bootstrap complete."
echo "Install Coolify with:"
echo "curl -fsSL https://cdn.coollabs.io/coolify/install.sh | sudo bash"
