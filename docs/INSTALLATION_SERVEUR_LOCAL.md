# Installer PopPilot sur les serveurs de MICROPOP (site + base + API)

Décision CDG (25/09/2026) : **les trois briques tournent chez MICROPOP**. La lenteur constatée
venait du trajet entre l'API et la base Supabase hébergée au Canada ; une fois la base sur le même
réseau que l'API, un tableau de bord qui prenait 60-85 s se calcule en quelques secondes.

Rien ne change dans le code : c'est la **même technologie** (Supabase = PostgreSQL + Auth). Seules
les adresses des fichiers `api/.env` et `web/.env.local` changent.

```
 Navigateurs (réseau MICROPOP)
        │ HTTPS (443)
        ▼
 ┌─────────────── serveur PopPilot ───────────────┐
 │ nginx  ── /          → site Next.js   :3000     │
 │        ── /supabase/ → Supabase (Kong) :8000    │  connexion, jetons
 │ API FastAPI :8001  ◄── appelée par Next seul   │  (jamais exposée)
 │ PostgreSQL (Supabase) :5432 ◄── API + Auth     │
 └─────────────────────────────────────────────────┘
```

## 1. Serveur

| Élément | Minimum conseillé |
|---|---|
| Système | Ubuntu Server 22.04 ou 24.04 LTS (Windows Server possible, voir §7) |
| Mémoire | 16 Go (PostgreSQL + Supabase ≈ 4 Go, API ≈ 2 Go, site ≈ 1 Go) |
| Disque | 200 Go SSD (base, archives de rapports, sauvegardes) |
| Logiciels | Docker + Docker Compose, Python 3.12+, Node.js 20+, nginx, git |

## 2. Base : Supabase auto-hébergé (Docker)

```bash
git clone --depth 1 https://github.com/supabase/supabase /opt/supabase
cd /opt/supabase/docker && cp .env.example .env
```
Dans `/opt/supabase/docker/.env`, remplacer AU MINIMUM :
- `POSTGRES_PASSWORD` : mot de passe fort (servira à `DATABASE_URL`) ;
- `JWT_SECRET` (40 caractères ou plus), puis générer `ANON_KEY` et `SERVICE_ROLE_KEY` avec ce
  secret (procédure « Generate API keys » de la documentation Supabase self-hosting) ;
- `SITE_URL=https://poppilot.micropop.local` et `API_EXTERNAL_URL=https://poppilot.micropop.local/supabase` ;
- `DASHBOARD_USERNAME` / `DASHBOARD_PASSWORD` (console d'administration).

```bash
docker compose pull && docker compose up -d
```

### Schéma PopPilot
Exécuter, dans l'ordre, dans l'éditeur SQL de la console (ou `psql`) :
`supabase/01_schema.sql` → `02_auth_rls.sql` → `05_…` → `06_…` → `07_…` → `08_ajout_collecte_epargne.sql`
(`03_utilisateurs_test.sql` et `04_verifier_cloisonnement.sql` : recette seulement).

### Reprise des données du cloud
Depuis un poste qui voit les deux bases :
```bash
pg_dump "postgresql://postgres:[MDP_CLOUD]@aws-0-ca-central-1.pooler.supabase.com:5432/postgres" \
  --schema=public --data-only --no-owner -Fc -f poppilot_public.dump
pg_restore --data-only --no-owner -d "postgresql://postgres:[MDP_LOCAL]@[SERVEUR]:5432/postgres" poppilot_public.dump
```
Comptes utilisateurs : les recréer dans la console (Authentication → Users), puis relier chaque
compte à sa ligne `utilisateur` (rôle, agence) avec `python api/lier_utilisateurs.py`. Recréer
plutôt que copier les mots de passe du cloud : c'est l'occasion de changer les comptes de démonstration.

## 3. API FastAPI

```bash
cd /opt/poppilot/api
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env
```
`api/.env` :
```
DATABASE_URL=postgresql://postgres:[POSTGRES_PASSWORD]@localhost:5432/postgres
SUPABASE_URL=https://poppilot.micropop.local/supabase
SUPABASE_JWT_SECRET=[JWT_SECRET du §2]      # auto-hébergé : jetons HS256 signés avec ce secret
POPPILOT_ARCHIVES_DIR=/srv/poppilot/archives
```
Vérifier : `.venv/bin/python tests/lancer_tous.py` (les tests utilisent des bases SQLite locales,
jamais la production), puis `.venv/bin/python verifier_supabase.py`.

Service permanent (`/etc/systemd/system/poppilot-api.service`) :
```ini
[Unit]
Description=PopPilot API
After=network.target docker.service
[Service]
WorkingDirectory=/opt/poppilot/api
ExecStart=/opt/poppilot/api/.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8001 --workers 3
Restart=always
[Install]
WantedBy=multi-user.target
```
`systemctl enable --now poppilot-api`. Port **8001** : le 8000 est pris par Supabase (Kong).
L'API n'écoute que sur 127.0.0.1 : seul le serveur Next l'appelle.

## 4. Site Next.js

```bash
cd /opt/poppilot/web && npm ci && cp .env.example .env.local
```
`web/.env.local` :
```
NEXT_PUBLIC_SUPABASE_URL=https://poppilot.micropop.local/supabase
NEXT_PUBLIC_SUPABASE_ANON_KEY=[ANON_KEY du §2]
NEXT_PUBLIC_POPPILOT_API=http://127.0.0.1:8001
NEXT_PUBLIC_POPPILOT_API_TIMEOUT_MS=60000
```
```bash
npm run build
```
Service `poppilot-web` identique au §3 avec `ExecStart=/usr/bin/npm run start -- -p 3000`.
Le mode démonstration s'éteint de lui-même dès que `.env.local` est renseigné.

## 5. nginx + HTTPS

```nginx
server {
  listen 443 ssl;
  server_name poppilot.micropop.local;
  ssl_certificate     /etc/ssl/poppilot.crt;      # certificat interne MICROPOP
  ssl_certificate_key /etc/ssl/poppilot.key;
  client_max_body_size 220m;                      # = serverActions.bodySizeLimit (imports CBS)
  location /supabase/ { proxy_pass http://127.0.0.1:8000/; proxy_set_header Host $host; }
  location /          { proxy_pass http://127.0.0.1:3000;  proxy_set_header Host $host;
                        proxy_read_timeout 300s; }
}
```

## 6. Sauvegardes (indispensable)

```bash
# /etc/cron.d/poppilot — chaque nuit à 2 h, 30 jours conservés
0 2 * * * root pg_dump "postgresql://postgres:[MDP]@localhost:5432/postgres" -Fc \
  -f /srv/sauvegardes/poppilot_$(date +\%F).dump && find /srv/sauvegardes -mtime +30 -delete
```
Sauvegarder aussi `/srv/poppilot/archives` (rapports déposés) et les deux fichiers `.env`.
Tester une restauration une fois par trimestre.

## 7. Variante Windows Server
Supabase : Docker Desktop (ou WSL2). API : même `.venv`, service via **NSSM**
(`nssm install PopPilotAPI C:\poppilot\api\.venv\Scripts\uvicorn.exe main:app --port 8001`).
Site : `npm run start` sous NSSM. Proxy : IIS (ARR) ou nginx pour Windows.

## 8. Recette de mise en service
1. `https://poppilot.micropop.local/login` → connexion CDG.
2. Page Import → réimporter un mois connu (ex. crédit de mai) : écran Crédit = Dashboard
   (encours 10 814 330,66 ; PAR30 1 052 118,05 ; 517 décaissements).
3. Profil AGENCE : ne voit que son agence (crédit, épargne, exports).
4. `GET /sante` de l'API (via le serveur) : base = PostgreSQL local, régime JWT actif.
