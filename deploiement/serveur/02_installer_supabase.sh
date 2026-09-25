#!/usr/bin/env bash
# =============================================================================
# PopPilot — SERVEUR MICROPOP, étape 2 : Supabase auto-hébergé (PostgreSQL + Auth).
#   sudo DOMAINE=poppilot.micropop.local bash deploiement/serveur/02_installer_supabase.sh
# Génère TOUS les secrets (mot de passe base, JWT, clés anon / service_role) et les
# écrit dans /opt/supabase/docker/.env. Ils sont réaffichés à la fin : les noter dans
# le coffre-fort de MICROPOP (jamais dans un courriel ni dans git).
# =============================================================================
set -euo pipefail
DOMAINE="${DOMAINE:-poppilot.micropop.local}"
DIR=/opt/supabase

[ -d "$DIR" ] || git clone --depth 1 https://github.com/supabase/supabase "$DIR"
cd "$DIR/docker"
[ -f .env ] && cp .env ".env.avant_$(date +%F_%H%M)"
cp .env.example .env

aleatoire() { openssl rand -base64 48 | tr -dc 'A-Za-z0-9' | head -c "$1"; }
PG_PASS=$(aleatoire 32)
JWT_SECRET=$(aleatoire 48)
DASH_PASS=$(aleatoire 20)

# Clés anon et service_role = jetons HS256 signés avec JWT_SECRET (validité 10 ans).
cle() {
  python3 - "$1" "$JWT_SECRET" <<'PY'
import base64, hashlib, hmac, json, sys, time
role, secret = sys.argv[1], sys.argv[2]
b64 = lambda b: base64.urlsafe_b64encode(b).rstrip(b"=").decode()
now = int(time.time())
tete = b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
corps = b64(json.dumps({"role": role, "iss": "supabase", "iat": now, "exp": now + 10 * 365 * 86400}).encode())
sig = b64(hmac.new(secret.encode(), f"{tete}.{corps}".encode(), hashlib.sha256).digest())
print(f"{tete}.{corps}.{sig}")
PY
}
ANON_KEY=$(cle anon)
SERVICE_KEY=$(cle service_role)

regler() { sed -i "s#^$1=.*#$1=$2#" .env; }
regler POSTGRES_PASSWORD "$PG_PASS"
regler JWT_SECRET "$JWT_SECRET"
regler ANON_KEY "$ANON_KEY"
regler SERVICE_ROLE_KEY "$SERVICE_KEY"
regler DASHBOARD_USERNAME "admin_poppilot"
regler DASHBOARD_PASSWORD "$DASH_PASS"
regler SITE_URL "https://$DOMAINE"
regler API_EXTERNAL_URL "https://$DOMAINE/supabase"
regler SUPABASE_PUBLIC_URL "https://$DOMAINE/supabase"
regler POOLER_TENANT_ID "poppilot"
regler SECRET_KEY_BASE "$(aleatoire 64)"
regler VAULT_ENC_KEY "$(aleatoire 32)"
# Pas de serveur de courriel : les comptes créés dans la console sont confirmés d'office.
regler ENABLE_EMAIL_AUTOCONFIRM "true"
regler DISABLE_SIGNUP "true"          # personne ne s'inscrit seul : les comptes sont créés par l'admin

docker compose pull
docker compose up -d
chmod 600 .env

cat <<FIN

=== Supabase démarré. SECRETS À CONSERVER (coffre-fort MICROPOP) ===
Mot de passe PostgreSQL : $PG_PASS
JWT_SECRET              : $JWT_SECRET
ANON_KEY                : $ANON_KEY
Console Studio          : https://$DOMAINE/supabase  (admin_poppilot / $DASH_PASS)
Connexion de l'API (pooler, mode session) :
  DATABASE_URL=postgresql://postgres.poppilot:$PG_PASS@127.0.0.1:5432/postgres
(la clé service_role reste dans /opt/supabase/docker/.env : jamais dans le site)
FIN
