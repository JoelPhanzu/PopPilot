# GUIDE DE DÉMARRAGE — Construire la plateforme MICROPOP avec Claude Code

## Contexte (à lire par Claude Code en premier)
Cette plateforme de pilotage pour une institution de microfinance (RDC) a été spécifiée et
prototypée en profondeur. TOUTE la logique métier est déjà :
- **documentée** dans `CLAUDE_CONNAISSANCE.md` (définitions PAR, barème provisions, cohérences FINA,
  règles AML, budget, multi-devises, historisation…) — c'est LA référence, ne rien inventer qui la contredise.
- **codée et validée au centime** dans les moteurs Python `engine/` et `socle/` (contre les fichiers
  réels de l'institution). Ces moteurs sont FIABLES. On les RÉUTILISE, on ne les réécrit pas.

## Objectif
Construire : **Next.js (front) + Supabase (base+auth) + API Python FastAPI (wrappe les moteurs)**.
Hébergement Hostinger. Migration PROGRESSIVE : Python garde les calculs, Next.js fait l'UI.

## Ordre de construction (IMPÉRATIF — valider chaque étape avant la suivante)

### Étape 1 — Supabase
1. Créer un projet Supabase.
2. Exécuter `SCHEMA_SUPABASE.sql` dans l'éditeur SQL (30 tables).
3. Ajouter une colonne `auth_uid uuid` à la table `utilisateur`, la lier à `auth.users`.
4. Activer RLS et créer les policies (modèle fourni dans le SQL) : cloisonnement par agence.
5. Créer les 4 rôles de test (DIRECTION, CDG, AGENCE, AUDIT).
→ VALIDER : un user AGENCE ne peut PAS lire les données d'une autre agence (tester en SQL).

### Étape 2 — API Python (FastAPI)
1. Créer une API FastAPI qui importe `engine/` et `socle/`.
2. Endpoints (un par moteur validé) :
   - POST /import/credit, /import/balance, /import/epargne  (upload fichier → Supabase)
   - GET  /par?arrete=YYYY-MM-DD                            (engine.par.calculer_par)
   - GET  /provisions?arrete=...                            (engine.derivation)
   - GET  /migrations?arrete=...&precedent=...              (engine.migrations)
   - GET  /etats-financiers?arrete=...                      (engine.etats_financiers)
   - GET  /indicateurs?arrete=...                           (engine.indicateurs)
   - GET  /epargne?arrete=...                               (engine.epargne)
   - GET  /budget?arrete=...&precedent=...&mois=...         (engine.budget)
   - POST /rapports/fina, /rapports/aml                     (génèrent le .xls, renvoient le fichier)
3. L'API lit/écrit Supabase (adapter socle/schema.py : pointer vers PostgreSQL Supabase au lieu de SQLite).
→ VALIDER : GET /par renvoie le MÊME PAR que les tests Python (écart nul vs Dashboard).

### Étape 3 — Next.js (front)
1. Projet Next.js + Supabase client + Supabase Auth (login).
2. Layout avec charte MICROPOP : logo (fourni), bleu foncé #0B3D5C (principal), cyan #00AEEA en accent léger, gris #58595B, "Je rêve, je réalise".
3. Page Crédit : appelle GET /par, affiche les indicateurs + tableau par agence. Cloisonnement via RLS.
→ VALIDER : login fonctionne, page crédit affiche les bons chiffres, agence cloisonnée.

### Étape 4 — Étendre
Pages : compta/indicateurs, épargne, budget, import CBS, rapports réglementaires. Export Excel.

### Étape 5 — Déploiement Hostinger
Front Next.js sur Hostinger. API Python : VPS ou service séparé. Variables d'env (clés Supabase).


## CHARTE GRAPHIQUE — PopPilot
- **Nom de la plateforme** : PopPilot (pilotage MICROPOP).
- **Signature** : « Je rêve, je réalise ».
- **Couleurs** :
  - Bleu principal (fond sidebar, en-têtes, barres) : **#0B3D5C** (bleu foncé, reposant)
  - Bleu secondaire (survols, dégradés) : **#1B5E86**
  - Cyan MICROPOP (accent LÉGER uniquement : liens, petits repères — jamais en aplat large) : **#00AEEA**
  - Gris texte : **#58595B**
  - Fonds clairs : **#F4F7FA** (panneaux), blanc pour les cartes
- ⚠️ Le cyan du logo (#00AEEA) est trop lumineux en aplat → l'utiliser avec parcimonie (accents),
  le bleu foncé #0B3D5C porte l'identité visuelle sur les grandes surfaces.

## POINTS DE VIGILANCE (erreurs déjà rencontrées — ne pas les refaire)
- **Multi-devises** : grand livre TOUJOURS en USD ; FINA en CDF (balance CDF directe, pas de conversion
  des éléments comptables) ; système de paiement PAS de conversion. Voir CLAUDE_CONNAISSANCE §multidevise.
- **Provisions/réalisé mensuel** = cumulé(N) − cumulé(N-1). La balance est cumulée depuis janvier.
- **PAR** vient du crédit, PAS du compte 39 (qui est le PAR1). Source unique.
- **Statut juridique inventaire** : 1=PP, 2=PM, 4=groupe.
- **date_arrete ≠ date_snapshot** : la date comptable (dernier jour ouvré) fait foi.
- **Formats fichiers** : .xls parfois = xlsx déguisé ; inventaire août a colonne "Mois année" qui décale ;
  Aout crédit a "Date_Cloture" en tête. Détecter, ne pas supposer.

## CE QUI RESTE À FAIRE (registre)
Voir `RESTE_A_FAIRE.md` : élaboration budget, corrections système de paiement, moteur de primes,
grille réintégration fiscale (DAF), effectifs RH.

## PREMIER PROMPT SUGGÉRÉ À CLAUDE CODE
"Lis CLAUDE_CONNAISSANCE.md, ARCHITECTURE_CIBLE.md et GUIDE_CLAUDE_CODE.md. On construit la plateforme
MICROPOP en Next.js + Supabase + API Python. Commence par l'étape 1 (Supabase) : aide-moi à créer le
projet, exécuter le schéma, et mettre en place le RLS de cloisonnement par agence. Les moteurs Python
dans engine/ sont validés, on les réutilisera via FastAPI — ne les réécris pas."
