#!/usr/bin/env bash
# setup-vps.sh - Run on a fresh Ubuntu 24.04 VPS
# Usage: curl -sSL <raw_url> | bash
set -euo pipefail

echo "=== Installing Docker ==="
apt-get update
apt-get install -y ca-certificates curl
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
  https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  > /etc/apt/sources.list.d/docker.list
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

echo "=== Enabling Docker ==="
systemctl enable --now docker

echo "=== Setting up project ==="
mkdir -p /opt/shark-no-kari
cd /opt/shark-no-kari

echo ""
echo "=== Done! ==="
echo "Next steps:"
echo "  1. Copy your project files to /opt/shark-no-kari/"
echo "  2. cp .env.example .env"
echo "  3. Point your domain's A record to this server's IP"
echo "  4. docker compose up -d --build"
echo "  5. Add https://yourdomain.com/mcp as a custom connector in claude.ai"
