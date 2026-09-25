#!/usr/bin/env bash
# =============================================================================
# PopPilot — SERVEUR MICROPOP, étape 5 : API FastAPI en service permanent.
#   sudo DOMAINE=poppilot.micropop.local PG_PASS='…' JWT_SECRET='…' \
#        bash deploiement/serveur/05_installer_api.sh
# (PG_PASS et JWT_SECRET : affichés par l'étape 2.)
# =============================================================================
set -euo pipefail
DOMAINE="${DOMAINE:-poppilot.micropop.local}"
: "${PG_PASS:?PG_PASS requis (étape 2)}"
: "${JWT_SECRET:?JWT_SECRET requis (étape 2)}"
cd /opt/poppilot/api

sudo -u poppilot python3 -m venv .venv
sudo -u poppilot .venv/bin/pip install --upgrade pip
sudo -u poppilot .venv/bin/pip install -r requirements.txt uvicorn

cat > .env <<ENV
DATABASE_URL=postgresql://postgres.poppilot:${PG_PASS}@127.0.0.1:5432/postgres
SUPABASE_URL=https://${DOMAINE}/supabase
SUPABASE_JWT_SECRET=${JWT_SECRET}
POPPILOT_ARCHIVES_DIR=/srv/poppilot/archives
ENV
chown poppilot:poppilot .env && chmod 600 .env

# Tables manquantes (init_db, idempotent) puis vérifications
sudo -u poppilot .venv/bin/python -c "from socle.schema import init_db; init_db(); print('tables OK')"
sudo -u poppilot .venv/bin/python tests/lancer_tous.py || echo "ATTENTION : campagne de tests non verte (bases de test locales)."

cp /opt/poppilot/deploiement/serveur/poppilot-api.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now poppilot-api
sleep 3
curl -fsS http://127.0.0.1:8001/sante && echo && echo "API en service sur 127.0.0.1:8001"
