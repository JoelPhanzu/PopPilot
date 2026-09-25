#!/usr/bin/env bash
# =============================================================================
# PopPilot — SERVEUR MICROPOP, étape 3 : poser le schéma PopPilot.
#   sudo bash deploiement/serveur/03_appliquer_schema.sh
# Exécute les scripts SQL du dépôt dans l'ordre, dans le conteneur « supabase-db ».
# (03_utilisateurs_test.sql et 04_verifier_cloisonnement.sql : recette seulement.)
# L'API crée ensuite les tables manquantes (init_db, idempotent) à l'étape 5.
# =============================================================================
set -euo pipefail
cd /opt/poppilot
for s in 01_schema.sql 02_auth_rls.sql 05_migration_balance_devise.sql \
         06_ajout_tables_ameliorations.sql 07_ajout_tables_modules.sql 08_ajout_collecte_epargne.sql \
         09_ajout_nom_client_epargne.sql 10_ajout_statut_juridique_epargne.sql; do
  echo "  -> $s"
  docker exec -i supabase-db psql -U postgres -d postgres -v ON_ERROR_STOP=1 -q < "supabase/$s"
done
echo "Schéma posé."
