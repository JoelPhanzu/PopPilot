#!/usr/bin/env bash
# =============================================================================
# PopPilot — SERVEUR MICROPOP : installer une nouvelle version du code.
#   sudo bash deploiement/serveur/mettre_a_jour.sh
# Sauvegarde d'abord, puis : récupération du code, dépendances, tests, reconstruction du
# site, redémarrage. Si les tests échouent, rien n'est redémarré (l'ancienne version tourne).
# Nouveau script SQL (supabase/09_….sql) : l'exécuter à la main avant (voir étape 3).
# =============================================================================
set -euo pipefail
/usr/local/bin/poppilot-sauvegarde
cd /opt/poppilot
sudo -u poppilot git pull --ff-only
sudo -u poppilot api/.venv/bin/pip install -r api/requirements.txt
(cd api && sudo -u poppilot .venv/bin/python -c "from socle.schema import init_db; init_db()")
(cd api && sudo -u poppilot .venv/bin/python tests/lancer_tous.py) || { echo "Tests en échec : mise à jour ARRÊTÉE."; exit 1; }
(cd web && sudo -u poppilot npm ci && sudo -u poppilot npm run build)
systemctl restart poppilot-api poppilot-web
echo "Mise à jour terminée."
