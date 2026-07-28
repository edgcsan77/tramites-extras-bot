#!/usr/bin/env bash
set -euo pipefail
apt update && apt upgrade -y
apt install -y git python3 python3-venv python3-pip postgresql postgresql-contrib redis-server nginx curl certbot python3-certbot-nginx
id tramites >/dev/null 2>&1 || useradd --system --create-home --shell /bin/bash tramites
systemctl enable --now postgresql redis-server nginx
