# PopPilot — Plateforme de pilotage MICROPOP

> « Je rêve, je réalise »

Plateforme de pilotage financier et commercial pour l'institution de microfinance MICROPOP (RDC).

## Architecture
- **`api/`** — API FastAPI qui expose les moteurs de calcul Python (VALIDÉS, ne pas réécrire).
- **`web/`** — interface Next.js (à créer, étape 4).
- **`supabase/`** — schéma PostgreSQL + RLS (cloisonnement par agence).
- **`docs/`** — architecture, guide de construction, modèle de données, registres.
- **`CLAUDE.md`** — connaissance métier complète (lu par Claude Code à chaque session).

## Principe directeur
La logique métier est déjà validée au centime contre les fichiers réels. On la RÉUTILISE via l'API,
on ne la réécrit pas. Le risque est dans les calculs, pas dans l'interface — d'où : valider chaque
calcul contre un chiffre connu (PAR30 mai = 1 052 118).

## Démarrage — voir docs/GUIDE_CLAUDE_CODE.md
### Base Supabase
Exécuter dans l'éditeur SQL, dans l'ordre :
1. `supabase/01_schema.sql` — les 30 tables
2. `supabase/02_auth_rls.sql` — auth liée à Supabase + cloisonnement par agence
3. `supabase/03_utilisateurs_test.sql` — 4 comptes de test (après création dans Authentication)
4. `supabase/04_verifier_cloisonnement.sql` — prouver le cloisonnement

### API en local
```
cd api
python -m venv .venv && .venv\Scripts\activate   # Windows
pip install -r requirements.txt
copy .env.example .env    # puis renseigner DATABASE_URL
uvicorn main:app --reload
```
Ouvrir http://localhost:8000/docs

## Validation
`GET /par?arrete=2026-05-30` doit renvoyer PAR30 global = 1 052 118 (chiffre validé).
