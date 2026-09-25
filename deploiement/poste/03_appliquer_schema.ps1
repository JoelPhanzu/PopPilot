# =============================================================================
# PopPilot — POSTE LOCAL, étape 3 : poser le schéma PopPilot dans la base locale.
#     powershell -ExecutionPolicy Bypass -File deploiement\poste\03_appliquer_schema.ps1
# Exécute les scripts SQL du dépôt DANS L'ORDRE (01, 02, 05 à 10), puis laisse
# l'API créer les éventuelles tables manquantes (init_db, idempotent).
# 03_utilisateurs_test.sql et 04_verifier_cloisonnement.sql : recette seulement, non exécutés.
# =============================================================================
$ErrorActionPreference = "Stop"
$racine = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $racine

$projet = (Select-String -Path "supabase\config.toml" -Pattern '^project_id\s*=\s*"(.+)"').Matches[0].Groups[1].Value
$conteneur = "supabase_db_$projet"
Write-Host "Conteneur de la base : $conteneur"

$scripts = "01_schema.sql", "02_auth_rls.sql", "05_migration_balance_devise.sql",
           "06_ajout_tables_ameliorations.sql", "07_ajout_tables_modules.sql",
           "08_ajout_collecte_epargne.sql", "09_ajout_nom_client_epargne.sql",
           "10_ajout_statut_juridique_epargne.sql"
foreach ($s in $scripts) {
    Write-Host "  -> $s"
    # docker cp puis psql -f : évite la conversion d'encodage du tube PowerShell (accents).
    docker cp "supabase\$s" "${conteneur}:/tmp/$s" | Out-Null
    docker exec $conteneur psql -U postgres -d postgres -v ON_ERROR_STOP=1 -q -f "/tmp/$s"
    if ($LASTEXITCODE -ne 0) { throw "Échec sur $s : lire le message ci-dessus." }
}

Write-Host "Création des tables manquantes par l'API (init_db)…"
$env:DATABASE_URL = "postgresql://postgres:postgres@127.0.0.1:54322/postgres"
& "api\.venv\Scripts\python.exe" -c "import sys; sys.path.insert(0, 'api'); from socle.schema import init_db; init_db(); print('  tables OK')"
Remove-Item Env:DATABASE_URL
Write-Host "Schéma posé."
