# =============================================================================
# PopPilot — POSTE LOCAL, étape 2 : Supabase local (PostgreSQL 17 + Auth) dans Docker.
#     powershell -ExecutionPolicy Bypass -File deploiement\poste\02_demarrer_supabase_local.ps1
# Supabase CLI via npx (aucune installation globale). Services NON utilisés par PopPilot
# exclus pour économiser la mémoire : temps réel, stockage de fichiers, fonctions, journaux.
# Première exécution : téléchargement des images (≈ 2-3 Go, 5-15 min).
# =============================================================================
$ErrorActionPreference = "Stop"
$racine = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)   # dossier PopPilot
Set-Location $racine

if (-not (Test-Path "supabase\config.toml")) {
    Write-Host "Initialisation du projet Supabase local (supabase\config.toml)…"
    # Le dossier supabase\ contient déjà les scripts SQL de PopPilot : init n'y touche pas.
    npx --yes supabase init --force
}

$exclus = "realtime,storage-api,imgproxy,edge-runtime,logflare,vector,supavisor"
Write-Host "Démarrage de Supabase local (services exclus : $exclus)…"
npx --yes supabase start -x $exclus
if ($LASTEXITCODE -ne 0) { throw "supabase start a échoué : Docker Desktop est-il lancé ?" }

Write-Host ""
Write-Host "=== Informations de connexion (à reporter par l'étape 5) ===" -ForegroundColor Cyan
npx --yes supabase status
Write-Host ""
Write-Host "Console d'administration (Studio) : http://127.0.0.1:54323"
