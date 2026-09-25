#!/usr/bin/env bash
# =============================================================================
# PopPilot — SERVEUR MICROPOP : restaurer une sauvegarde (à tester chaque trimestre).
#   sudo bash deploiement/serveur/08_restaurer.sh /srv/sauvegardes/poppilot_2026-10-01.dump
# ÉCRASE les données actuelles : l'API et le site sont arrêtés pendant l'opération.
# =============================================================================
set -euo pipefail
DUMP="${1:?chemin du fichier .dump}"
read -r -p "Restaurer $(basename "$DUMP") ÉCRASE la base PopPilot. Taper OUI : " ok
[ "$ok" = "OUI" ] || { echo "Abandon."; exit 1; }

systemctl stop poppilot-web poppilot-api
docker cp "$DUMP" supabase-db:/tmp/restauration.dump
docker exec supabase-db pg_restore -U supabase_admin -d postgres --clean --if-exists --no-owner \
       /tmp/restauration.dump || echo "Avertissements de pg_restore : vérifier les écrans."
docker exec supabase-db rm -f /tmp/restauration.dump
systemctl start poppilot-api poppilot-web
echo "Restauration terminée : contrôler la page Import (journal) et un écran connu."
