# =============================================================================
# PopPilot — POSTE LOCAL, étape 4 : copier les données du cloud (Supabase) vers le poste.
#     powershell -ExecutionPolicy Bypass -File deploiement\poste\04_copier_donnees_cloud.ps1
# Lit l'adresse du cloud dans api\.env.cloud (copie de sauvegarde faite par l'étape 5)
# ou, à défaut, dans api\.env. Le cloud n'est QUE LU (pg_dump) : rien n'y est modifié.
# pg_dump 17 tourne dans un conteneur : aucune installation de PostgreSQL sur le poste.
# La table « utilisateur » n'est PAS copiée : ses comptes pointent sur les identifiants
# Auth du cloud ; on les recrée en local (étape 6).
# =============================================================================
$ErrorActionPreference = "Stop"
$racine = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $racine

$fichierEnv = if (Test-Path "api\.env.cloud") { "api\.env.cloud" } else { "api\.env" }
$url = (Select-String -Path $fichierEnv -Pattern '^DATABASE_URL=(.+)$').Matches[0].Groups[1].Value.Trim()
if ($url -notmatch "supabase\.com") { throw "$fichierEnv ne pointe pas sur le cloud Supabase : rien à copier." }
Write-Host "Source (cloud) : $($url.Split('@')[-1])"

$projet = (Select-String -Path "supabase\config.toml" -Pattern '^project_id\s*=\s*"(.+)"').Matches[0].Groups[1].Value
$conteneur = "supabase_db_$projet"
$dossier = Join-Path $racine "sauvegardes"
New-Item -ItemType Directory -Force $dossier | Out-Null
$dump = "cloud_$(Get-Date -Format yyyy-MM-dd_HHmm).dump"

Write-Host "1/2 Extraction des données du cloud (pg_dump 17)…"
docker run --rm -v "${dossier}:/dump" postgres:17 pg_dump $url --schema=public --data-only `
    --no-owner --no-privileges --exclude-table-data=public.utilisateur -Fc -f "/dump/$dump"
if ($LASTEXITCODE -ne 0) { throw "pg_dump a échoué (mot de passe ? réseau ?)" }

Write-Host "2/2 Chargement dans la base locale…"
docker cp (Join-Path $dossier $dump) "${conteneur}:/tmp/$dump" | Out-Null
# supabase_admin (super-utilisateur local) : nécessaire pour --disable-triggers (clés étrangères
# désactivées le temps du chargement, l'ordre des tables n'importe plus).
docker exec $conteneur pg_restore -U supabase_admin -d postgres --data-only --no-owner `
    --disable-triggers "/tmp/$dump"
if ($LASTEXITCODE -ne 0) { Write-Host "pg_restore signale des avertissements : vérifier avec l'étape 7 (comparaison)." -ForegroundColor Yellow }
Write-Host "Copie terminée. Fichier conservé : sauvegardes\$dump"
