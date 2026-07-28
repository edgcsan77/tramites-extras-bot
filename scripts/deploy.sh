#!/usr/bin/env bash
set -euo pipefail
cd /opt/tramites-extras-bot
git pull --ff-only
/opt/tramites-extras-bot/.venv/bin/pip install -r requirements.txt
set -a; source .env; set +a
PSQL_URL="${DATABASE_URL/postgresql+psycopg:/postgresql:}"
psql "$PSQL_URL" -f migrations/001_initial.sql
systemctl restart tramites-extras-web
systemctl restart 'tramites-extras-worker@*' || true
systemctl --no-pager --full status tramites-extras-web
