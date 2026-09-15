# Connexion aux projets existants — PopPilot

Tu as déjà créé :
- **GitHub** : https://github.com/JoelPhanzu/PopPilot
- **Supabase** : projet `qpklywwzpukzjaclhxwd`

## 1. Pousser le code sur GitHub
Dans le dossier PopPilot (terminal VS Code) :
```
git remote add origin https://github.com/JoelPhanzu/PopPilot.git
git push -u origin main
```
(Le dépôt local est déjà initialisé avec un premier commit.)

## 2. Monter la base Supabase
Dans Supabase → SQL Editor, exécuter DANS L'ORDRE :
1. `supabase/01_schema.sql`   → crée les 30 tables
2. `supabase/02_auth_rls.sql` → auth liée + RLS (cloisonnement par agence)
3. Créer 4 users dans Authentication → Users (dg, cdg, victoire, audit) + noter leurs UUID
4. `supabase/03_utilisateurs_test.sql` → remplacer les <UUID_...> par les vrais, puis exécuter
5. `supabase/04_verifier_cloisonnement.sql` → prouver le cloisonnement

## 3. Connecter l'API à Supabase
Récupérer l'URL de connexion : Supabase → Project Settings → Database → Connection string (URI).
```
cd api
copy .env.example .env
```
Ouvrir `.env` et coller l'URL dans DATABASE_URL (avec le mot de passe de la base).
⚠️ Le fichier .env est ignoré par git (jamais publié). Ne mets JAMAIS tes clés dans le code.

## 4. Lancer l'API
```
cd api
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```
Ouvrir http://localhost:8000/docs et tester GET /par?arrete=2026-05-30
→ doit renvoyer PAR30 global = 1 052 118.

## 5. Importer les données (une fois l'API connectée à Supabase)
Les fichiers sources réels (crédit, balance, épargne) restent EN LOCAL (jamais sur git).
Utiliser les scripts d'import via l'API, ou en local avec DATABASE_URL défini.
