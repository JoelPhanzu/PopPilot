#!/usr/bin/env bash
# =============================================================================
# PopPilot — SERVEUR MICROPOP : sauvegarde nocturne (base + archives + configuration).
# Installation (chaque nuit à 2 h, 30 jours conservés) :
#   sudo cp deploiement/serveur/07_sauvegarde.sh /usr/local/bin/poppilot-sauvegarde
#   echo '0 2 * * * root /usr/local/bin/poppilot-sauvegarde' | sudo tee /etc/cron.d/poppilot
# COPIE_DISTANTE : dossier monté d'un AUTRE serveur / NAS (une sauvegarde sur le même
# disque ne protège pas d'une panne du serveur).
# =============================================================================
set -euo pipefail
DEST=/srv/sauvegardes
COPIE_DISTANTE="${COPIE_DISTANTE:-}"
JOUR=$(date +%F)

docker exec supabase-db pg_dump -U postgres -d postgres -Fc -f /tmp/poppilot.dump
docker cp supabase-db:/tmp/poppilot.dump "$DEST/poppilot_$JOUR.dump"
docker exec supabase-db rm -f /tmp/poppilot.dump
tar czf "$DEST/archives_$JOUR.tgz" -C /srv/poppilot archives
tar czf "$DEST/config_$JOUR.tgz" /opt/poppilot/api/.env /opt/poppilot/web/.env.local /opt/supabase/docker/.env
chmod 600 "$DEST"/*_"$JOUR".*

[ -n "$COPIE_DISTANTE" ] && cp "$DEST"/*_"$JOUR".* "$COPIE_DISTANTE"/
find "$DEST" -name '*.dump' -mtime +30 -delete
find "$DEST" -name '*.tgz'  -mtime +30 -delete
echo "Sauvegarde $JOUR terminée."
