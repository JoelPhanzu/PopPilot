#!/usr/bin/env bash
# =============================================================================
# PopPilot — SERVEUR MICROPOP, étape 1 : préparer Ubuntu Server 22.04 / 24.04.
#   sudo bash deploiement/serveur/01_preparer_serveur.sh
# Installe Docker, Python, Node.js 20, nginx, git et le client PostgreSQL 17 ;
# crée l'utilisateur système « poppilot » et les dossiers de travail.
# =============================================================================
set -euo pipefail

apt-get update
apt-get install -y ca-certificates curl gnupg git nginx python3 python3-venv python3-pip \
                   openssl cron ufw

# Docker (dépôt officiel)
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  > /etc/apt/sources.list.d/docker.list
# Node.js 20 (NodeSource)
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
# Client PostgreSQL 17 (dépôt PGDG) : pg_dump doit être de la même version que la base
echo "deb http://apt.postgresql.org/pub/repos/apt $(. /etc/os-release && echo "$VERSION_CODENAME")-pgdg main" \
  > /etc/apt/sources.list.d/pgdg.list
curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc | gpg --dearmor -o /etc/apt/keyrings/pgdg.gpg
sed -i 's#^deb http#deb [signed-by=/etc/apt/keyrings/pgdg.gpg] http#' /etc/apt/sources.list.d/pgdg.list

apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin nodejs postgresql-client-17

# Utilisateur de service et dossiers
id poppilot >/dev/null 2>&1 || useradd --system --create-home --shell /bin/bash poppilot
usermod -aG docker poppilot
mkdir -p /opt/poppilot /srv/poppilot/archives /srv/sauvegardes
chown -R poppilot:poppilot /opt/poppilot /srv/poppilot /srv/sauvegardes

# Pare-feu : seul HTTPS (et SSH) ouvert au réseau ; API, base et Supabase restent internes.
ufw allow OpenSSH
ufw allow 443/tcp
ufw --force enable

echo "Serveur prêt. Étape suivante : cloner le dépôt dans /opt/poppilot puis 02_installer_supabase.sh"
echo "  sudo -u poppilot git clone https://github.com/JoelPhanzu/PopPilot.git /opt/poppilot"
