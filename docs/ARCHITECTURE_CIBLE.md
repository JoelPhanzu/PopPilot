# ARCHITECTURE CIBLE — Plateforme MICROPOP (Next.js + Supabase + API Python)

## Vue d'ensemble
```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│  Next.js    │────▶│  API Python  │────▶│  Moteurs métier │
│  (front web)│     │  (FastAPI)   │     │  engine/ socle/ │
│  Hostinger  │     │  calculs     │     │  (VALIDÉS)      │
└──────┬──────┘     └──────────────┘     └─────────────────┘
       │
       ▼
┌─────────────┐
│  Supabase   │  PostgreSQL + Auth + RLS (cloisonnement par agence)
└─────────────┘
```

## Principe directeur : NE PAS réécrire les moteurs
Les moteurs Python (dossier `engine/` et `socle/`) sont **validés au centime** contre les fichiers
réels de l'institution. On les EXPOSE via FastAPI, on ne les réécrit PAS en JavaScript.
Le risque du projet est dans la LOGIQUE MÉTIER, pas dans l'interface. Cette logique est capturée
dans CLAUDE.md et testée dans tests/. La préserver est prioritaire.

## Répartition des responsabilités
- **Supabase** : stockage des faits (crédit, balance, épargne, transactions, budget), dimensions,
  paramètres, utilisateurs. Authentification. Row Level Security (RLS) pour le cloisonnement agence.
- **API Python (FastAPI)** : reçoit les demandes de calcul, lit Supabase (ou reçoit les données),
  applique les moteurs `engine/`, renvoie les résultats. Gère aussi l'import des fichiers CBS et la
  génération des rapports réglementaires (.xls FINA, AML…).
- **Next.js** : interface. Login via Supabase Auth. Pages par domaine (crédit, compta, épargne,
  budget, rapports). Appelle l'API pour les calculs, lit Supabase pour l'affichage direct.
- **Hostinger** : héberge le front Next.js (et éventuellement l'API via VPS/Node).

## Rôles & habilitations (RLS Supabase)
- DIRECTION, CDG : accès total (toutes agences, import, génération rapports)
- AGENCE : cloisonné à SON agence (RLS filtre au niveau base — sécurité réelle, pas cosmétique)
- AUDIT : lecture seule, toutes agences
Table `utilisateur` : login, rôle, agence, actif. Lier à auth.users de Supabase.

## Multi-devises (RÈGLE STRICTE)
- Montants stockés en devise d'origine (USD ou CDF).
- Conversion SEULEMENT quand le rapport cible l'exige :
  - FINA : tout en CDF (balance CDF directe, sans conversion des éléments comptables)
  - AML : transferts (grand livre, TOUJOURS en USD) convertis en CDF ; opérations espèces CDF+USD
  - Système de paiement : PAS de conversion (chaque devise dans sa colonne)
- Taux de change DATÉ (table param_taux_change). Août 2026 : 2263.57.

## Historisation (STRUCTURANT)
- Chaque import = snapshot daté. date_arrete (comptable, fait foi) ≠ date_snapshot (import).
- Réalisé/dotation mensuel = cumulé(N) − cumulé(N-1). La balance arrive en cumulé.
- Consultable par date, mois par mois. Comparaison de 2 périodes quelconques.

## Ordre de construction recommandé (pour Claude Code)
1. Schéma Supabase (tables + RLS + auth) — voir SCHEMA_SUPABASE.sql
2. API Python FastAPI qui wrappe engine/ (endpoints : /par, /provisions, /etats-financiers, /fina...)
3. Next.js : login Supabase + 1 page (crédit) qui appelle l'API → valider la chaîne complète
4. Étendre : autres pages, import CBS, génération rapports, export Excel
5. Déploiement Hostinger
