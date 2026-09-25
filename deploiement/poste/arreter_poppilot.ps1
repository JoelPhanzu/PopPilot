# =============================================================================
# PopPilot — arrêter l'API, le site et Supabase local (libère la mémoire du poste).
#     powershell -ExecutionPolicy Bypass -File deploiement\poste\arreter_poppilot.ps1
# Les données restent dans le volume Docker : rien n'est perdu à l'arrêt.
# =============================================================================
$racine = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $racine
Get-CimInstance Win32_Process | Where-Object {
    $_.CommandLine -match "uvicorn(\.exe)? main:app" -or $_.CommandLine -match "next start|next-server"
} | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Write-Host "API et site arrêtés."
if ((Test-Path "supabase\config.toml") -and (Get-Command docker -ErrorAction SilentlyContinue)) {
    npx --yes supabase stop
    Write-Host "Supabase local arrêté (données conservées)."
}
