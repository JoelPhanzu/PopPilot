# =============================================================================
# PopPilot — sauvegarde de la base LOCALE du poste (et restauration).
#   Sauvegarder :  powershell -ExecutionPolicy Bypass -File deploiement\poste\sauvegarder.ps1
#   Planifier (chaque jour à 13 h, PC allumé) :
#                  powershell -ExecutionPolicy Bypass -File deploiement\poste\sauvegarder.ps1 -Planifier
#   Restaurer :    powershell -ExecutionPolicy Bypass -File deploiement\poste\sauvegarder.ps1 -Restaurer sauvegardes\poppilot_2026-10-01.dump
# Copie : mettre $Copie sur un disque externe ou un dossier OneDrive/SharePoint : une
# sauvegarde sur le même disque ne protège pas d'une panne du poste.
# =============================================================================
param([switch]$Planifier, [string]$Restaurer, [string]$Copie = "", [int]$Jours = 30)
$ErrorActionPreference = "Stop"
$racine = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $racine
$projet = (Select-String -Path "supabase\config.toml" -Pattern '^project_id\s*=\s*"(.+)"').Matches[0].Groups[1].Value
$conteneur = "supabase_db_$projet"
$dossier = Join-Path $racine "sauvegardes"
New-Item -ItemType Directory -Force $dossier | Out-Null

if ($Planifier) {
    $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-ExecutionPolicy Bypass -File `"$PSCommandPath`""
    $declencheur = New-ScheduledTaskTrigger -Daily -At 13:00
    Register-ScheduledTask -TaskName "PopPilot - sauvegarde" -Action $action -Trigger $declencheur -Force | Out-Null
    Write-Host "Tâche planifiée « PopPilot - sauvegarde » créée (chaque jour à 13 h)."
    return
}

if ($Restaurer) {
    $nom = Split-Path $Restaurer -Leaf
    $ok = Read-Host "Restaurer $nom ÉCRASE les données PopPilot de la base locale. Taper OUI"
    if ($ok -ne "OUI") { Write-Host "Abandon."; return }
    docker cp $Restaurer "${conteneur}:/tmp/$nom" | Out-Null
    docker exec $conteneur pg_restore -U supabase_admin -d postgres --clean --if-exists --no-owner "/tmp/$nom"
    Write-Host "Restauration terminée (vérifier les écrans, puis la page Import)."
    return
}

$fichier = "poppilot_$(Get-Date -Format yyyy-MM-dd_HHmm).dump"
docker exec $conteneur pg_dump -U postgres -d postgres --schema=public -Fc -f "/tmp/$fichier"
if ($LASTEXITCODE -ne 0) { throw "pg_dump a échoué : Supabase local est-il démarré ?" }
docker cp "${conteneur}:/tmp/$fichier" (Join-Path $dossier $fichier) | Out-Null
docker exec $conteneur rm "/tmp/$fichier"
Write-Host "Sauvegarde : sauvegardes\$fichier"
if ($Copie) { Copy-Item (Join-Path $dossier $fichier) $Copie; Write-Host "Copie : $Copie" }
Get-ChildItem $dossier -Filter "poppilot_*.dump" | Where-Object LastWriteTime -lt (Get-Date).AddDays(-$Jours) | Remove-Item
