#!/usr/bin/env bash
# =============================================================================
# PopPilot — SERVEUR MICROPOP, étape 6 : site Next.js en service permanent.
#   sudo DOMAINE=poppilot.micropop.local ANON_KEY='…' bash deploiement/serveur/06_installer_site.sh
# (ANON_KEY : affichée par l'étape 2. Jamais la clé service_role ici.)
# =============================================================================
set -euo pipefail
DOMAINE="${DOMAINE:-poppilot.micropop.local}"
: "${ANON_KEY:?ANON_KEY requise (étape 2)}"
cd /opt/poppilot/web

cat > .env.local <<ENV
NEXT_PUBLIC_SUPABASE_URL=https://${DOMAINE}/supabase
NEXT_PUBLIC_SUPABASE_ANON_KEY=${ANON_KEY}
NEXT_PUBLIC_POPPILOT_API=http://127.0.0.1:8001
NEXT_PUBLIC_POPPILOT_API_TIMEOUT_MS=60000
ENV
chown poppilot:poppilot .env.local && chmod 600 .env.local

sudo -u poppilot npm ci
sudo -u poppilot npm run build

cp /opt/poppilot/deploiement/serveur/poppilot-web.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now poppilot-web
echo "Site en service sur 127.0.0.1:3000 (publié par nginx, étape 7)."
