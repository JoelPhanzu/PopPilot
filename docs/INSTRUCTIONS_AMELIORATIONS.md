# PopPilot — Instructions pour les améliorations (chantiers 1 à 7)

## ⚠️⚠️ RÈGLE FONDAMENTALE — ROSTER MENSUEL & ORPHELIN (ne jamais contourner)
Toute performance (décaissement, PAR, recouvrement, primes, productivité) n'est calculée QUE pour
les agents figurant sur la LISTE DU MOIS fournie à PopPilot (roster + objectifs) — agents de crédit,
superviseurs, agents de recouvrement. La liste fait AUTORITÉ.
Tout agent ABSENT de la liste (parti, non réaffecté) → ses chiffres basculent AUTOMATIQUEMENT dans
le PORTEFEUILLE ORPHELIN (jamais dans la performance d'un autre, jamais en prime).
Chaîne : n° dossier → agent de l'encours → sur la liste du mois ? oui=performance / non=orphelin.
Détail complet : voir moteurs/REGLE_ROSTER_ORPHELIN.md
(Agences fermées comme Goma = portefeuille gelé, traité à part.)



> À lire par Claude Code avant de commencer. Compléter la plateforme existante.

## ⚠️ RÈGLE ABSOLUE : ADDITIF, JAMAIS DESTRUCTIF
La base de données CONTIENT DÉJÀ DES DONNÉES. La plateforme est en production.
- **Ne recrée JAMAIS les tables existantes.** Nouvelles tables uniquement via `CREATE TABLE IF NOT EXISTS`.
- **N'efface aucune donnée.** Le script `06_ajout_tables_ameliorations.sql` est strictement additif et rejouable.
- **Ne remplace aucun moteur existant.** Les nouveaux moteurs (fournis dans `moteurs/`) s'ajoutent à côté.
- **Ne casse aucun endpoint existant.** On AJOUTE des endpoints, on ne modifie pas les anciens.
- Plateforme évolutive = on empile, on ne reconstruit pas.

## Contexte
Les moteurs de calcul (crédit, compta, épargne, FINA, AML...) sont validés au centime.
Les améliorations = enrichir les tableaux de bord, ajouter des axes d'analyse, de nouveaux
domaines (compte de résultat par agence, intérêts par agent, primes), et finaliser les rapports.

Ordre recommandé (du plus rapide au plus lourd) :
A. Import des données (préalable) → B. Tableau de bord crédit enrichi (1,2)
→ C. Compte de résultat par agence (3) → D. Primes (4) → E. Rapports réglementaires (7)
→ F. Traitement SAGE (5) → G. Exports (6, transversal).

---

## CHANTIER 1 & 2 — Tableau de bord crédit enrichi + productivité
Afficher TOUS les KPI du reporting, avec des AXES DE VENTILATION sélectionnables.

**KPI à exposer** (moteurs existants dans api/engine/) :
encours, PAR1/30/90, provisions, coût du risque, migrations, croissance, décaissements
(nombre + volume), recouvrement, **intérêts encaissés** (nouveau, voir chantier 2),
productivité (décaissé / effectif), nombre de clients, nombre de crédits.

**AXES DE VENTILATION** (filtres, combinables) :
- par **agent de crédit**
- par **superviseur**
- par **agence**
- par **sexe** (colonnes Femme/Homme de l'extraction)
- par **produit** (colonne Produit crédit) — SÉLECTION MULTIPLE
- par **durée** :
    - Court terme = durée max 12 mois **+ le crédit de groupe (LISANGA)**
    - Moyen terme = durée > 12 mois à 24 mois

**Implémentation** : les moteurs calculent déjà global + par agence. Ajouter des paramètres de
filtre (agent, superviseur, sexe, produits[], durée) qui restreignent l'ensemble des prêts AVANT calcul.
Un seul moteur générique de filtrage sur fait_credit, appliqué à tous les KPI.

**Productivité par agent/superviseur/agence** : décaissé ÷ effectif, encours géré, PAR de son
portefeuille, épargne, décaissements, remboursements, migrations, croissance, intérêts encaissés.
→ un « profil de performance » par agent, réutilisé pour les primes (chantier 4).

---

## CHANTIER 2 (source) — Intérêts encaissés par agent/superviseur/agence
Le fichier des remboursements a n° dossier + intérêts remboursés, PAS la hiérarchie.
L'encours crédit a la hiérarchie. → JOINTURE sur le numéro de dossier.

**Moteur fourni** : `moteurs/interets_par_agent.py` (lit les remboursements, ventile par agent/
superviseur/agence via l'encours du mois, rattachement en cascade + non-rattachés).
**Table fournie** : `fait_remboursement_encaisse` (voir SQL) — stocke les remboursements
AVEC la hiérarchie déjà résolue à l'import.

**À l'import** : pour chaque remboursement, retrouver l'agent/superviseur/agence via fait_credit
(numéro de dossier) et enregistrer. Dossiers introuvables (soldés) → "(non rattaché)", signalé.

---

## CHANTIER 3 — Compte de résultat par agence
La balance par agence n'existe pas dans SAGE. À la place, le CDG fournit CHAQUE FIN DE MOIS
un fichier "COMPTE_RESULTAT_<mois>_isolé.xlsx" déjà ventilé par agence.

**Structure FIXE** (feuille Feuil2) :
- colonne A = intitulé du poste
- colonnes B..G = VICTOIRE, OZONE, GOMA, LUBUMBASHI, MASINA, GOMBE
- colonne H = MICROPOP (consolidé)
- lignes clés : TOTAL PRODUITS, TOTAL CHARGES, RESULTAT COMPTABLE

**Moteur fourni** : `moteurs/import_compte_resultat_agence.py` (import + contrôle de cohérence :
MICROPOP doit = somme des 6 agences ; sinon alerte).
**Table fournie** : `compte_resultat_agence` (poste × agence × mois, historisée).

**Page à créer** : compte d'exploitation par agence, avec le RÉSULTAT par agence en évidence
(vert si bénéfice, rouge si perte). Exemple juillet : Victoire +38 316, Lubumbashi +35 763,
Masina +5 507 (bénéfices) ; Ozone −12 499, Goma −19 057, Gombe −23 232 (pertes).

---

## CHANTIER 4 — Calcul des primes  ⚠️ CORRECTION PRIMES
IMPORTANT : la prime NE se calcule PAS sur les intérêts. Les intérêts encaissés servent à mesurer
la PROFITABILITÉ de l'agent (produits = intérêts+commissions+pénalités, face aux charges).
La PRIME se calcule sur : décaissement, PAR, épargne, nombre de clients, volume d'encours,
type de produit (GL=Crédit LISANGA / IL=individuel), avec le correcteur PAR.
PME = décaissement >= 15 000.
→ Moteur CONSTRUIT et VALIDÉ : moteurs/moteur_primes.py (31/31 agents au centime vs fichier mai).
Couvre "AC et SUP" (agents crédit + superviseurs). Cascade : éligibilité encours (IL/GL) → type de
prime (volume/nombre) → prime crédit × correcteur PAR → prime couverture → total + motif.
RESTE : les 7 autres catégories de personnel (superviseur épargne, recouvrement, support, direction...).
Moteur PAS encore construit (dans le registre). Barème et correcteur PAR déjà en base
(param_bareme_prime). Consomme le profil de performance par agent (chantier 2).

**Logique (déjà définie, §60 de CLAUDE.md)** :
- Prime = base (volume, nombre, couverture) × correcteur PAR.
- Correcteur PAR : PAR ≤ 3% → ×1 ; 3-5% → ×0,7 ; 5-7% → ×0,5 ; > 7% → ×0 (prime annulée).
- Un agent productif mais à PAR élevé perd sa prime → indexation sur la qualité du portefeuille.
**Table fournie** : `campagne_prime` (historise les paramètres appliqués, traçabilité).
Le PAR par agent vient du chantier 1 (source unique).

---

## CHANTIER 5 — Traitement du journal des opérations CBS pour SAGE
Le journal des opérations du CBS doit être RETRAITÉ avant import dans SAGE (comptabilité).
⚠️ Les règles de transformation restent à recueillir auprès du CDG (chantier neuf).
**Table fournie** : `journal_sage_traite` (traçabilité des traitements).
À spécifier avec le CDG avant de coder : format d'entrée CBS, format attendu par SAGE, règles
de mapping/agrégation.

---

## CHANTIER 6 — Exports
Ajouter/améliorer les formats d'export sur toutes les pages :
- Excel (.xlsx) — le principal, pour les retraitements hors plateforme
- PDF pour les rapports de synthèse (Direction, CA)
- CSV pour l'interopérabilité
Transversal : un composant d'export réutilisable sur chaque tableau.

---

## CHANTIER 7 — Finaliser les rapports réglementaires
- **FINA** : compléter l'écriture .xls (gabarit BCC). Il manque le n° de ligne exact des groupes
  solidaires dans F6 (le CDG doit le fournir). Ventilations F5/F11 par sous-ligne.
- **AML** : les groupes (3 566, 732 M CDF) — le CDG fournit le n° de ligne du formulaire LBC-FT.
  Sections secteur/alertes complétées par la Conformité.
- **Système de paiement** : corrections à faire (voir docs/RESTE_A_FAIRE.md). Ordre colonnes
  Volume/Valeur à confirmer.

---

## Fichiers de référence fournis
- `moteurs/import_compte_resultat_agence.py` — chantier 3 (testé, résultat par agence exact)
- `moteurs/interets_par_agent.py` — chantier 2 (testé, 344 116 d'intérêts août)
- `06_ajout_tables_ameliorations.sql` — nouvelles tables, ADDITIF (IF NOT EXISTS)
- `exemples_donnees/` — vrais fichiers pour caler la structure (compte de résultat, remboursements)

## Chiffres de validation (garde-fous)
- Compte de résultat juillet : Victoire +38 316,10 ; total agences = MICROPOP (contrôle).
- Intérêts remboursés août : 344 115,98 (total, à ventiler par agent).
- Rappel généraux : PAR30 mai = 1 052 118 ; actif juillet = 12 592 520.

## CHANTIER — CLASSEMENT CLIENTS (Top N)
Moteur CONSTRUIT et testé : moteurs/moteur_classement_clients.py.
Affiche les N meilleurs/pires clients (agrégé par client) selon : encours, PAR (relance),
décaissement (période), épargne, fidélité. N paramétrable. Doctrine flux/stock. Cloisonné agence.
Page à créer : "Clients" avec choix du critère, du N, du sens (meilleurs/pires) et des filtres.
Confidentialité : données nominatives, réservées aux rôles habilités, cloisonnées par agence.
