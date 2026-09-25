# =============================================================================
# PopPilot — démarrer les 3 briques sur le poste : base (si locale), API, site.
#     powershell -ExecutionPolicy Bypass -File deploiement\poste\demarrer_poppilot.ps1
# L'API et le site s'ouvrent chacun dans leur fenêtre (fermer la fenêtre = arrêter).
# Site en mode production (next build puis start) : plus rapide et plus léger que « dev ».
# Ajouter -Reconstruire après une mise à jour du code du site.
# =============================================================================
param([switch]$Reconstruire)
$ErrorActionPreference = "Stop"
$racine = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $racine

$local = (Get-Content "api\.env" -Raw) -match "127\.0\.0\.1:54322"
if ($local) {
    Write-Host "Base locale : démarrage de Supabase (Docker Desktop doit être lancé)…"
    npx --yes supabase start -x "realtime,storage-api,imgproxy,edge-runtime,logflare,vector,supavisor" | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Supabase local n'a pas démarré : lancer Docker Desktop puis réessayer." }
} else {
    Write-Host "Base : cloud Supabase (api\.env)."
}

Write-Host "API FastAPI → http://127.0.0.1:8000"
Start-Process powershell -ArgumentList "-NoExit", "-Command",
    "Set-Location '$racine\api'; .\.venv\Scripts\uvicorn.exe main:app --host 127.0.0.1 --port 8000 --workers 2"

Set-Location "$racine\web"
if ($Reconstruire -or -not (Test-Path ".next\BUILD_ID")) {
    Write-Host "Construction du site (1-3 min)…"
    npm run build
    if ($LASTEXITCODE -ne 0) { throw "Échec de la construction du site." }
}
Write-Host "Site → http://localhost:3000"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$racine\web'; npm run start"
Start-Sleep -Seconds 6
Start-Process "http://localhost:3000/login"
