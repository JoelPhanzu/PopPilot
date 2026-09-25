# =============================================================================
# PopPilot — POSTE LOCAL, étape 5 : faire pointer l'API et le site vers une base.
#     powershell -ExecutionPolicy Bypass -File deploiement\poste\05_basculer_base.ps1 -Cible local
#     powershell -ExecutionPolicy Bypass -File deploiement\poste\05_basculer_base.ps1 -Cible cloud
# Garde deux jeux de configuration côte à côte et active l'un OU l'autre :
#   api\.env.cloud / api\.env.poste      →  api\.env         (actif)
#   web\.env.cloud / web\.env.poste      →  web\.env.local   (actif)
# Premier passage : l'actuel api\.env (cloud) est sauvegardé en .env.cloud, et la
# configuration locale est construite à partir de « supabase status ».
# Redémarrer l'API et le site après une bascule (demarrer_poppilot.ps1).
# Ces fichiers contiennent des secrets : ignorés par git (.env.*).
# =============================================================================
param([Parameter(Mandatory = $true)][ValidateSet("local", "cloud")][string]$Cible)
$ErrorActionPreference = "Stop"
$racine = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $racine

# Sauvegarde unique de la configuration cloud actuelle.
if (-not (Test-Path "api\.env.cloud") -and (Test-Path "api\.env")) { Copy-Item "api\.env" "api\.env.cloud" }
if (-not (Test-Path "web\.env.cloud") -and (Test-Path "web\.env.local")) { Copy-Item "web\.env.local" "web\.env.cloud" }

if ($Cible -eq "local" -and -not (Test-Path "api\.env.poste")) {
    Write-Host "Lecture des clés de Supabase local…"
    $statut = npx --yes supabase status -o env | Out-String
    function Lire($cle) {
        $m = [regex]::Match($statut, "(?m)^$cle=""?([^""\r\n]+)""?")
        if (-not $m.Success) { throw "Clé $cle absente de 'supabase status' : Supabase local est-il démarré ?" }
        return $m.Groups[1].Value
    }
    $jwt = Lire "JWT_SECRET"
    $anon = Lire "ANON_KEY"
    $archives = Join-Path $racine "archives_depot"
    New-Item -ItemType Directory -Force $archives | Out-Null
    @"
# PopPilot — API sur la base LOCALE du poste (Supabase local, Docker)
DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:54322/postgres
SUPABASE_URL=http://127.0.0.1:54321
SUPABASE_JWT_SECRET=$jwt
POPPILOT_ARCHIVES_DIR=$archives
"@ | Set-Content "api\.env.poste" -Encoding utf8
    @"
# PopPilot — site sur la base LOCALE du poste
NEXT_PUBLIC_SUPABASE_URL=http://127.0.0.1:54321
NEXT_PUBLIC_SUPABASE_ANON_KEY=$anon
NEXT_PUBLIC_POPPILOT_API=http://127.0.0.1:8000
NEXT_PUBLIC_POPPILOT_API_TIMEOUT_MS=60000
"@ | Set-Content "web\.env.poste" -Encoding utf8
    Write-Host "  Créés : api\.env.poste, web\.env.poste"
}

$suffixe = if ($Cible -eq "local") { "poste" } else { "cloud" }
Copy-Item "api\.env.$suffixe" "api\.env" -Force
Copy-Item "web\.env.$suffixe" "web\.env.local" -Force
Write-Host "Base active : $Cible. Redémarrer l'API et le site (demarrer_poppilot.ps1)." -ForegroundColor Cyan
