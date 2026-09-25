#!/usr/bin/env bash
# =============================================================================
# PopPilot — SERVEUR MICROPOP, étape 4 : reprendre les données existantes.
#   Depuis le cloud Supabase :
#     sudo SOURCE_URL='postgresql://postgres.[REF]:[MDP]@aws-0-ca-central-1.pooler.supabase.com:5432/postgres' \
#          bash deploiement/serveur/04_reprendre_donnees.sh
#   Depuis une sauvegarde du poste local (fichier .dump de sauvegarder.ps1) :
#     sudo DUMP=/srv/sauvegardes/poppilot_2026-10-01.dump bash deploiement/serveur/04_reprendre_donnees.sh
# La SOURCE n'est que lue. La table « utilisateur » n'est pas reprise : ses comptes
# pointent sur les identifiants Auth de l'ancienne base (recréés à l'étape 6).
# =============================================================================
set -euo pipefail
cd /srv/sauvegardes
if [ -n "${SOURCE_URL:-}" ]; then
  DUMP="reprise_$(date +%F_%H%M).dump"
  echo "Extraction de la source (lecture seule)…"
  pg_dump "$SOURCE_URL" --schema=public --data-only --no-owner --no-privileges \
          --exclude-table-data=public.utilisateur -Fc -f "$DUMP"
fi
[ -n "${DUMP:-}" ] && [ -f "$DUMP" ] || { echo "Indiquer SOURCE_URL=… ou DUMP=fichier.dump"; exit 2; }

echo "Chargement dans la base du serveur…"
docker cp "$DUMP" supabase-db:/tmp/reprise.dump
# supabase_admin : super-utilisateur, requis pour --disable-triggers (clés étrangères
# suspendues le temps du chargement). --data-only : le schéma vient de l'étape 3.
# pg_restore n'a pas d'option pour écarter une table : on filtre sa LISTE de contenu
# (utile pour une sauvegarde du poste, qui contient la table utilisateur).
docker exec supabase-db sh -c "pg_restore -l /tmp/reprise.dump | grep -v 'TABLE DATA public utilisateur ' > /tmp/reprise.liste"
docker exec supabase-db pg_restore -U supabase_admin -d postgres --data-only --no-owner \
       --disable-triggers -L /tmp/reprise.liste /tmp/reprise.dump || \
  echo "Avertissements de pg_restore : contrôler avec comparer_bases.py (étape 7)."
docker exec supabase-db rm -f /tmp/reprise.dump /tmp/reprise.liste
echo "Reprise terminée."
