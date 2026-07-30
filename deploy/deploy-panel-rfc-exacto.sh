#!/usr/bin/env bash
set -Eeuo pipefail
cd /opt/tramites-extras-bot
OLD=$(git rev-parse HEAD)
git fetch origin main
git reset --hard origin/main
PY=./.venv/bin/python3
$PY -m py_compile app/main.py app/models.py app/panel.py app/panel_data.py app/panel_theme.py app/panel_rfc_main_view.py app/panel_rfc_mini_view.py app/admin_multibot.py
$PY -c "from app.main import app; print('IMPORT_OK', len(app.routes))"
systemctl restart tramites-extras-web.service
sleep 3
systemctl is-active --quiet tramites-extras-web.service || { git reset --hard "$OLD"; systemctl restart tramites-extras-web.service; exit 1; }
systemctl status tramites-extras-web.service --no-pager -l
echo DEPLOY_PANEL_RFC_EXACTO_OK
