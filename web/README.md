# PopPilot — front Next.js

Interface de la plateforme de pilotage MICROPOP (etape 3 du guide
`docs/GUIDE_CLAUDE_CODE.md`). Le front **affiche**, il ne calcule pas : tous les
chiffres viennent de l'API FastAPI (`api/`), qui expose les moteurs Python
valides au centime.

## Demarrer

```bash
cd web
npm install
cp .env.example .env.local   # puis remplacer les [A_REMPLIR]
npm run dev                  # http://localhost:3000
```

Pour des chiffres reels, lancer aussi l'API dans un autre terminal :

```bash
cd api
uvicorn main:app --reload    # http://localhost:8000
```

Sans `.env.local` renseigne, l'ecran de connexion propose un **mode
demonstration** (donnees d'illustration, un bouton par role). Ce mode s'eteint
des que Supabase est configure et n'existe jamais en production.

## Variables d'environnement (`web/.env.local`, ignore par git)

| Variable | Role |
|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | URL **racine** du projet Supabase, sans chemin ni slash final (voir ci-dessous) |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Cle **anonyme** (jamais `service_role` dans le front) |
| `NEXT_PUBLIC_POPPILOT_API` | API FastAPI (defaut `http://localhost:8000`) |

> **Piege courant.** `NEXT_PUBLIC_SUPABASE_URL` doit etre l'URL RACINE
> (`https://xxxx.supabase.co`), pas l'URL REST copiee depuis la console
> (`https://xxxx.supabase.co/rest/v1/`). supabase-js ajoute lui-meme le chemin
> de chaque service ; avec `/rest/v1` deja dans la variable, la connexion part
> vers `/rest/v1/auth/v1/token` et Supabase repond
> **« Invalid path specified in request URL »**. Le front ramene desormais la
> valeur a son origine et affiche un avertissement sur `/login` tant que
> `.env.local` n'est pas corrige.

## Ecrans

| Route | Contenu |
|---|---|
| `/` | Redirige vers `/credit` (connecte) ou `/login` |
| `/login` | Connexion Supabase Auth + mode demonstration |
| `/credit` | Encours, PAR1 / PAR30 / PAR90, provisions, PAR30 par agence (graphique + tableau) |
| `/import` | Chargement des fichiers du CBS dans le socle + journal des imports (DIRECTION / CDG) |

### `/import` — charger les extractions du CBS

Le formulaire est **construit a partir de `GET /import/domaines`** : domaines,
extensions acceptees, champs obligatoires et facultatifs viennent de l'API. Il n'y
a donc pas deux listes a garder en phase — ajouter un domaine cote moteur le fait
apparaitre a l'ecran. Si l'API ne repond pas, aucun formulaire n'est affiche :
mieux vaut aucun envoi qu'un envoi qui n'arrivera nulle part.

Le fichier passe par le **serveur Next** (action serveur), jamais directement du
navigateur a l'API : l'API n'a donc pas besoin d'etre joignable depuis
l'internet. C'est ce qui impose `serverActions.bodySizeLimit` dans
`next.config.ts` (220 Mo), a tenir coherent avec `POPPILOT_IMPORT_MAX_MO` cote
API (200 Mo par defaut). Un inventaire epargne fait ~170 000 comptes.

Re-importer le meme arrete **remplace** le chargement precedent (idempotence du
socle) : l'ecran annonce combien de lignes ont ete remplacees.

## Cloisonnement par role

Quatre roles : `DIRECTION`, `CDG`, `AUDIT` (acces total) et `AGENCE` (cloisonne).
Le role est lu **cote serveur** dans la table `utilisateur` (colonne `auth_uid`),
comme le font `pp_role()` cote RLS et `utilisateur_courant()` cote API — jamais
dans les metadonnees du jeton.

Trois verrous, dans cet ordre :

1. **RLS Supabase** — protege les acces directs a la base (`supabase/02_auth_rls.sql`).
2. **Filtre dans l'API** — l'API se connecte en `postgres`, qui ignore le RLS
   (`api/auth_supabase.py`). Ne jamais retirer ce filtre.
3. **Front** — `src/lib/roles.ts` (miroir exact du module Python) et le contexte
   `src/composants/ContexteSession.tsx` : un role `AGENCE` ne voit que sa ligne,
   et le total affiche est la somme de ses seules lignes, jamais l'agregat
   institution. Le front ne protege pas la donnee, il evite de la reclamer.

## Structure

```
src/
├── app/
│   ├── layout.tsx           # charte, typographie systeme
│   ├── page.tsx             # redirection
│   ├── login/               # ecran de connexion + actions serveur
│   ├── credit/              # tableau de bord credit
│   └── import/              # import des fichiers du CBS (page, formulaire, action)
├── composants/              # coquille, cartes, graphique, tableau, contexte de session
├── lib/
│   ├── config.ts            # env + detection du gabarit [A_REMPLIR]
│   ├── roles.ts             # roles et cloisonnement (miroir de auth_supabase.py)
│   ├── session.ts           # profil courant (serveur)
│   ├── api.ts               # appel de l'API FastAPI
│   ├── credit.ts            # types /par et /provisions
│   ├── import.ts            # types et libelles du domaine import (client)
│   ├── import-serveur.ts    # appels /import/domaines et /imports (serveur)
│   ├── demo.ts              # donnees d'illustration (mode demonstration)
│   ├── format.ts            # montants, taux, dates (fr-FR)
│   └── supabase/            # clients navigateur et serveur
└── proxy.ts                 # rafraichissement de session + garde de navigation
```

> Next.js 16 : le `middleware` s'appelle desormais `proxy`, et `cookies()`,
> `params` et `searchParams` sont asynchrones.

## Charte

Bleu principal `#0B3D5C` · bleu secondaire `#1B5E86` · cyan `#00AEEA` (accent
leger : liens, filets, focus — jamais en aplat large) · gris texte `#58595B` ·
fond `#F4F7FA`. Signature : « Je reve, je realise ».

## Verifier

```bash
npx tsc --noEmit   # types
npx eslint .       # lint
npm run build      # build de production
```
