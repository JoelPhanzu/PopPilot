# =============================================================================
# PopPilot — POSTE LOCAL, étape 1 : vérifier et installer les prérequis.
# À lancer dans PowerShell en ADMINISTRATEUR, depuis le dossier PopPilot :
#     powershell -ExecutionPolicy Bypass -File deploiement\poste\01_prerequis.ps1
# Installe Docker Desktop (s'il manque) et limite la mémoire de WSL2 : sur un poste
# de 8 Go, sans limite, Docker prendrait la mémoire du site et de l'API.
# =============================================================================
$ErrorActionPreference = "Stop"

function Verifier($nom, $commande) {
    try { $v = & $commande 2>$null; Write-Host ("  OK  {0,-16} {1}" -f $nom, ($v | Select-Object -First 1)) ; return $true }
    catch { Write-Host ("  --  {0,-16} absent" -f $nom) -ForegroundColor Yellow ; return $false }
}

Write-Host "Prérequis PopPilot (poste local)"
$ram = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB, 1)
$libre = [math]::Round((Get-PSDrive C).Free / 1GB, 0)
Write-Host "  Mémoire : $ram Go ; disque C: libre : $libre Go"
if ($ram -lt 8)  { Write-Host "  ATTENTION : moins de 8 Go de mémoire. Fermer les autres applications pendant l'usage." -ForegroundColor Yellow }
if ($libre -lt 40) { Write-Host "  ATTENTION : moins de 40 Go libres (20 mois d'inventaires ≈ 1,5 Go + images Docker ≈ 10 Go + sauvegardes)." -ForegroundColor Yellow }

Verifier "Python" { python --version } | Out-Null
Verifier "Node.js" { node --version } | Out-Null
Verifier "git" { git --version } | Out-Null
$wsl = Verifier "WSL" { wsl --version }
$docker = Verifier "Docker" { docker --version }

if (-not $wsl) {
    Write-Host "Installation de WSL2 (redémarrage nécessaire ensuite)…"
    wsl --install --no-distribution
}
if (-not $docker) {
    Write-Host "Installation de Docker Desktop via winget…"
    winget install -e --id Docker.DockerDesktop --accept-package-agreements --accept-source-agreements
    Write-Host "Redémarrer Windows, lancer Docker Desktop une fois (accepter les conditions), puis relancer ce script." -ForegroundColor Cyan
}

# Limiter la mémoire de WSL2 (Docker) : 4 Go sur un poste de 8 Go.
$wslconfig = Join-Path $env:USERPROFILE ".wslconfig"
if (-not (Test-Path $wslconfig)) {
    @"
[wsl2]
memory=4GB
processors=4
swap=4GB
"@ | Set-Content -Path $wslconfig -Encoding ascii
    Write-Host "  Créé : $wslconfig (WSL2 limité à 4 Go). Appliqué au prochain 'wsl --shutdown'."
} else {
    Write-Host "  $wslconfig existe déjà : vérifier qu'il contient memory=4GB."
}
Write-Host "Terminé."
