# CLAUDE.md — Plateforme de pilotage MICROPOP (guide de dépôt)

> Lu au début de chaque session Claude Code. La **base de connaissances métier complète** est dans
> `docs/` (CLAUDE_CONNAISSANCE.md + 4 livrables de structuration). Ce fichier-ci = guide du dépôt.

## Ce qu'on construit
Un **socle de données unique multi-domaines** (crédit, épargne, comptabilité, transactions, budget,
rémunération) + des **rapports comme vues** de ce socle. Objectif : remplacer une constellation de
fichiers Excel par un outil cohérent, historisé et fiable. Voir `docs/04_BACKLOG_CONSTRUCTION.md`.

## Principes non négociables (docs §0)
1. **Stocker des FAITS datés, jamais d'indicateur calculé.** Les KPI se recalculent (catalogue §Livrable 2).
2. **Deux dates distinctes** : `date_snapshot` (import) ≠ `date_arrete` (date comptable, **fait foi**, §69.2).
3. **Devise d'origine** stockée ; conversion USD→CDF dérivée d'un taux daté.
4. **Paramètres versionnés à date d'effet** (barème, objectifs, taux, normes, réintégrations…).
5. **Ne stocker que le brut** (crédit : colonnes SIG A→AF) ; dérivations recalculées.
6. **Encours crédit calculé UNE fois** = invariant qui rend tous les rapports cohérents.

## Structure du dépôt (architecture PopPilot — Next.js/Supabase/API)
```
PopPilot/
├── CLAUDE.md                 # cette connaissance métier (lue par Claude Code)
├── api/                      # API FastAPI qui EXPOSE les moteurs (ne pas réécrire les calculs)
│   ├── main.py               # endpoints (/par, /provisions, /etats-financiers...)
│   ├── auth_supabase.py      # sécurité : vérifie le jeton Supabase + cloisonnement agence (API)
│   ├── engine/               # moteurs de calcul VALIDÉS (par, provisions, migrations, fina, aml...)
│   ├── socle/                # schéma DB (schema.py → DATABASE_URL Supabase), historisation, calendrier
│   ├── ingest/               # imports CBS (crédit, balance, épargne, budget...)
│   └── tests/                # tests de validation (garde-fous)
├── web/                      # interface Next.js (login + dashboard crédit) — charte PopPilot
├── supabase/                 # 01_schema.sql, 02_auth_rls.sql, 03_utilisateurs, 04_verifier
├── assets/                   # logo MICROPOP
└── docs/                     # architecture, guide, modèle de données, registres
```
**Cloisonnement à DEUX niveaux** : RLS Supabase (accès directs) + filtre dans l'API (appels FastAPI,
car l'API se connecte en 'postgres' qui ignore le RLS — cf. api/auth_supabase.py).


## État d'avancement
- ✅ **Phase 0** — socle : 27 tables, historisation, calendrier ouvré RDC, paramètres, tests verts.
- ✅ **Phase 1 (quasi complète)** — crédit, tout validé écart nul vs Excel :
  - Import `fait_credit` (dates JJ/MM/AAAA en texte gérées) — avril (7 935) + mai (7 984).
  - **PAR1/30/90** aux 4 niveaux = Dashboard.
  - **Provisions** (barème) : 938 244,42 = fichier.
  - **Croissance** mai/avril : −0,8904 % = Dashboard.
  - **Coût du risque + migrations** : 1 119,37 + 5 tranches = Dashboard. ⚠️ Migrations classées par
    tranche de DÉPART (code M-1), pas d'arrivée — subtilité du fichier reproduite fidèlement.
  - **Décaissements** (filtre intervalle de dates) : 517 prêts / 1 070 672 = Dashboard.
  - **Roster + objectifs** importés (`dim_employe` + `param_objectif`) depuis OBJECTIF.xlsx.
  - **Orphelins** : moteur OK. ⚠️ Le fichier OBJECTIF ne couvre pas tous les agents actifs
    (Goma : 0 agent au roster vs 21 en activité) → 19,8 % du portefeuille classé orphelin.
    **À clarifier avec le CDG : roster complet requis, ou objectifs ≠ roster ?**
  - **Statut d'agence** : dim_agence porte statut/date_fermeture/motif ; Goma = FERMEE (M23).
    Portefeuille gelé (1,45 M) isolé, exclu des orphelins. Agences gérables (ajout/fermeture/réouverture).
  - **Roster exhaustif** confirmé : orphelins restants = vrais anciens agents (ex. MUKENDI 413 prêts).
  - ✅ **Banc d'essai Streamlit** (bench/app.py) : tableau de bord crédit complet, filtre de dates,
    démarre et répond. **PHASE 1 COMPLÈTE.**

## Démarrer
```bash
pip install sqlalchemy
python socle/seed_parametres.py     # crée la base + paramètres
python tests/test_socle.py          # tests socle
python tests/test_phase1_par.py     # validation crédit (écart nul vs Excel)
streamlit run bench/app.py          # tableau de bord visuel
```

## Conventions
- Tester les calculs (`tests/`) **avant** de construire l'UI.
- Jamais de vraies données clients au dépôt : fixtures anonymisées dans `tests/fixtures/`.
- Frontière stricte : `socle/ engine/ ingest/` n'importent JAMAIS `bench/ web/`.
- Toute nouvelle définition d'indicateur se documente dans `docs/02_CATALOGUE_INDICATEURS.md` avant d'être codée.
- Un import du 4 mai portant l'arrêté du 30 avril est rangé en **avril** (date_arrete fait foi).

## Points de doctrine (docs §67-69) — tranchés
- **Résultat net** = comptable − IBP ; IBP = (comptable + réintégrations) × 30 %, à l'arrêté annuel.
  Grille de réintégration paramétrable (§67). Taux effectif variable (≈77 % en 2025).
- **Solvabilité** : dénominateur = total actif de la période (pas de RWA).
- **Prorata** : jours **ouvrés**. Défaut : **samedi ouvré, dimanche non**. Fériés RDC récurrents
  intégrés (`socle/calendrier.py`). Reports d'arrêté ministériel et jours exceptionnels **saisissables**
  (`declarer_exception`, `reporter_ferie`), priorité absolue sur les règles automatiques.

## À collecter (intrants manquants)
- Grille complète des réintégrations fiscales (DAF).
- Fériés RDC récurrents : ✅ intégrés (`socle/calendrier.py`). Reports annuels d'arrêté à saisir
  au fil de l'eau (`reporter_ferie`) ; jours exceptionnels via `declarer_exception`.


## Notes métier récentes (à intégrer au modèle)
- **Statut d'agence** : une agence peut être ACTIVE, FERMÉE ou SUSPENDUE. Ex. **Goma = fermée**
  (occupation M23) → pas d'agents actifs, c'est NORMAL. Son portefeuille (encours ~1,45 M, PAR)
  reste réel et déclarable à la BCC, mais NE doit PAS être classé « orphelin » ni évalué en
  performance d'agents. Distinguer 3 cas : (1) agence active + agents ; (2) agence fermée sans
  agents = portefeuille gelé à suivre ; (3) vrais orphelins = agent parti dans une agence qui
  fonctionne. → ajouter `statut` + `date_fermeture` à dim_agence ; exclure les agences fermées
  de la détection d'orphelins.
- **Roster ≠ objectifs** : le fichier OBJECTIF est une liste PARTIELLE (agents avec objectifs sur
  agences actives), pas le roster complet. Il faut un **roster complet séparé** (tous les agents
  actifs par agence) pour la détection d'orphelins. Objectifs et roster sont deux intrants distincts.
- **Décaissement à la date près** : validé. L'outil filtre par intervalle [début;fin] quelconque
  (démontré : mois, quinzaines, semaine, jour — 134+383=517). Supérieur au DailyTool/Analyse Crédit
  qui ne voient que « le mois en cours ». Même principe extensible aux stocks dès qu'il y a plusieurs
  snapshots datés.


## Provision spéciale agences fermées (Goma) — décision DAF, saisie manuelle
- Goma : encours ACTIF (recouvrement local via mobile money → Kinshasa), **rééchelonné** périodiquement
  pour ne pas plomber le PAR. Provisionné **1 %/mois cumulé → 100 % en 5 ans**.
- Ce montant n'est **PAS calculé** par l'outil : prélèvement **manuel des comptables + accord DAF**.
- Table `provision_manuelle` (date_arrete, agence, montant, note, saisi_par, horodatage).
  Saisie via `ingest/provision_manuelle.py` ou le tableau de bord (section dédiée).
- `engine/derivation.py` : pour toute agence à provision manuelle, le **barème auto ne s'applique
  pas** (pas de double comptage) ; le montant saisi **remplace** et s'ajoute au total. Traçable.


## Coût du risque, radiation & clôture annuelle (précisions CDG)
- **Coût du risque = différentiel de provision** (provision M − provision M-1), calculé **prêt par prêt**
  (jointure numero_dossier), pas sur les totaux bruts. Sur mai : **+1 119** (dégradation nette du
  portefeuille existant). La simple différence des totaux (−5 467) inclut entrées/sorties de prêts et
  n'est PAS le coût du risque. Le différentiel n'a de sens qu'EN COURS D'ANNÉE (combien provisionner
  de plus ce mois-ci).
- **À la clôture (31/12)** : on ne raisonne plus en différentiel mais en **stock total de provisions**
  constitué pour couvrir le risque. → prévoir un mode « clôture annuelle » distinct du suivi mensuel.
- **Radiation (write-off) au 31/12** : tout crédit en retard **≥ 361 jours** est radié (sorti du bilan),
  provisionné à 100 %. → `engine` : à la clôture, isoler l'encours ≥361j comme « à radier ».
- **Rentrée sur créance non recouvrable** : le radié continue d'être recouvré ; les sommes récupérées
  sur un crédit déjà radié = **produit** « rentrée sur créance non recouvrable » (compte de produit).
  → à modéliser dans le domaine comptable (Phase 2) + rapprochement avec le recouvrement.
- **PAR1 = portefeuille à risque GLOBAL** (tout crédit ≥1 jour de retard) : à afficher au **premier
  plan**, à égalité avec PAR30 (norme réglementaire) et PAR90. Mai : PAR1 = 1 188 447 (10,99 %).
- **Provision Goma = ADDITIVE** : part barème (sur retard résiduel) + complément manuel DAF. Goma
  reste INCLUSE dans encours/PAR/provisions ; seule la détection d'orphelins l'exclut.


## Phase 2 — Comptabilité (états financiers) ✅ VALIDÉE
- Import balance SAGE **brute** (`ingest/import_balance.py`) → `fait_balance` (420 comptes).
  Le **solde net est calculé** (Débit − Crédit) quand absent → plus besoin du fichier magique.
- Moteur `engine/etats_financiers.py` : mapping préfixe→agrégat (§40), bilan + CR, conversion USD→CDF.
- **Validé écart nul vs fichier magique** : total actif 12 592 520,01 · résultat net 142 477,78 USD ·
  fonds propres 4 697 575,57 · bilan équilibré · 0 compte non mappé.
- ⚠️ **Anomalie du fichier source** (§43) : le CR magique convertit le CDF au taux 2268,33 alors que
  le bilan utilise 2268,75 → écart 0,02 %. Notre moteur applique **un seul taux** (plus cohérent) ;
  on ne reproduit pas l'imprécision. Montants USD = source de vérité.
- Encours crédit bilan (31+32+39) = 10 974 953,62 (juillet) extrait correctement → invariant X-1
  vérifiable dès que balance + extraction crédit du même mois seront chargées.
- Comptes mixtes ACTIF/PASSIF : le signe du solde net décide du côté (reproduit fidèlement).
- Reste Phase 2 : import grand livre (2.4) ; puis Phase 3 (indicateurs prudentiels, FINA).


## Phase 3 — Indicateurs prudentiels (bien avancée)
- 3 mois chargés (crédit+balance) : **déc 2025, mai 2026, juillet 2026** → moyennes de période OK.
- **PAR depuis Phase 1** (source unique) : PAR crédit juillet (PAR1 1 348 331) = compte 39 balance
  juillet, au centime → **invariant X-1 vérifié en réel**. A1_PAR30 = vrai PAR30 (≥31j).
- **Fonds propres — DEUX VERSIONS (décision CDG)** :
  - **Version 1 hors résultat** (comptes 10-14) : base 4 555 098, prud. 4 802 771 → **pilote TOUS
    les ratios** (résultat non affecté ≠ capital). C'est la version réglementaire stricte.
  - **Version 2 avec résultat affecté** (base + résultat) : base 4 697 576, prud. 4 945 249 →
    **information seule, n'entre jamais dans les ratios**. (Note : la réf fichier 4 945 662 = version 2
    prud., le fichier mélangeait donc implicitement.)
  - Prudentiels = base + compte 18.
- **Moyennes de période** (ROE/ROA/efficacité/rendement) : (arrêté + 31/12 précédent)/2, opérationnel.
- **Concordent** : C4, D1, D2, D3, capitalisation, PAR. Disponibles = 56+57 ; cautions (27) à part.
- Restent : B2 emprunteurs/agent, E4 liquidité (dépôts à vue épargne), E6 couverture emplois MLT.


## Phase Épargne ✅ VALIDÉE
- Import inventaire dépôt (`ingest/import_epargne.py`) : **169 799 comptes** en 15 s (CSV ; UTF-8 BOM,
  virgule décimale). → `fait_epargne`.
- **Classification produits (règle CDG)** : à terme = Pop Monnaie A Terme + EducaPop A Terme ;
  obligatoire = Pop Monnaie Nantie + Caution Groupes ; à vue = le reste. Groupe = Transitoire Groupe
  (id 15,17) + Caution (id 20).
- Moteur `engine/epargne.py` : encours (converti USD au taux daté), ventilation type/devise/groupe,
  nb épargnants. Juillet : total **6 368 439 USD** ; à vue 1 837 270, à terme 2 909 946, oblig. 1 621 222.
- **Épargnants 67 147** ≈ réf FINA 67 120 ✓. Dépôts à vue → **débloque liquidité E4**.
- **Cohérence bilan** : épargne inventaire 6 368 439 ≈ dépôts bilan (33+34) 6 406 264 → écart 0,6 % ✓.
- ⚠️ **Balance partielle** : la balance des fichiers `*_Encours_et_balance` (420 comptes) N'A PAS les
  comptes de dépôts 33/34 → utiliser `BALANCE_ok` (447 comptes, complète) pour la compta. À vérifier
  côté export SAGE (filtre ?).


## Phase 3 COMPLÈTE — 17/17 indicateurs prudentiels calculés
- **E4 liquidité branchée** via épargne : dispo(56+57) ÷ dépôts à vue = 75,61 % (réf 74,85 %) ✓.
- **B2 emprunteurs/agent** : emprunteurs actifs (crédit) ÷ agents (roster). 8 121 emprunteurs.
  ⚠️ Nb agents : roster OBJECTIF = 39, mais RH officiel = 29 (réf FINA). Le nb d'agents pour ce
  ratio réglementaire doit venir du **rapport RH mensuel** (à saisir), pas du fichier objectifs.
- Les 17 calculés : A1 PAR30 10,81 %, A2, B1, B2, C1-C4, D1-D3, E1-E5 + E4. (E6 couverture emplois
  MLT à affiner : distinction >1 an dans crédit/DAT.)
- Pour juillet complet : utiliser **BALANCE_ok** (complète) + crédit + épargne + objectifs juillet.


## Phase FINA (Rapport 3) — 9 feuilles, taux manuel
- **CORRECTION** : le fichier `Juillet_2026_Encours_et_balance` est COMPLET (balance avec dépôts
  33/34 = 6 406 264 USD). Mon diagnostic « balance partielle » était FAUX (base mal reconstruite).
  Un seul fichier combiné suffit pour tout le FINA.
- `engine/fina.py` génère **9 feuilles** : F0, F1, F2, F3, F5, F6, F7, F10, F11.
- **TAUX CDF SAISI MANUELLEMENT** (`ingest/taux_change.saisir_taux`) : le générateur REFUSE de
  produire sans taux (jamais figé). Modèle identique à la provision Goma.
- Montants CDF : total 24 899 426 025 et retard 3 059 025 409 = **exacts** au gabarit. Ventilation
  CT/MT peut se compenser légèrement (classement inter-extraction, total identique). Groupe LISANGA
  3 172 238 623 = gabarit.
- **4 cohérences inter-feuilles vertes** : F5=bilan, F11=bilan, crédit=bilan, résultat F1=F0.
- À affiner : périmètre exact F7 Nostri (comptes 56x), F2 MT (intérêts inclus ?), F10 secteur.
- Reste : écriture effective dans le gabarit .xls des 9 feuilles ; F2 éléments de portée (RH).


## FINA — écriture du gabarit .xls (assemblage final)
- `engine/fina_ecriture.py` : copie le gabarit BCC (MFII*.xls) et remplit F0, F1, F5 en CDF depuis
  le socle (xlutils/xlwt). Résultat net calculé depuis classes 6/7 (compte 13 = 0 en cours d'année),
  injecté en V1.F0p.25.
- **F0/F1 au franc CDF près** : crédit CT 14 983 445 551, MT 6 856 955 065, épargne 8 035 667 550,
  capital 6 638 948 750, résultat net 366 203 898, produits clientèle 6 143 233 759. Tous ✓.
- Fichier `.xls` généré et vérifié → `FINA_juillet_2026_genere.xls`.
- Reste : F2 (éléments de portée, RH), F6/F7/F10 annexes, et remplir les colonnes détaillées de F5/F11
  (ventilation par sous-ligne). Le cœur (F0, F1, cohérences) est produit.


## FINA COMPLET — F0, F1, F2, F5, F11 remplis ✅
- `engine/fina_ecriture.py` génère le .xls BCC complet depuis le socle, en CDF :
  - **F0** bilan, **F1** compte de résultat (résultat net 366 203 898 calculé classes 6/7).
  - **F5** ventilation crédit Client/Groupe : CT 14 983 445 551 (client 12 526 939 427 + groupe
    2 456 506 124), MT, retard. Total 24 899 426 025.
  - **F11** balance âgée : encours + retard + tranches.
  - **F2** éléments de portée : emprunteurs (socle), épargnants (socle), employés + agents (saisie RH
    via param `rh={'nb_employes','nb_agents_credit'}`).
- Tout au franc CDF près. Fichier: `FINA_juillet_2026_complet.xls`.
- Reste (annexes secondaires) : F6/F7/F10, sous-lignes détaillées F5/F11 par produit. Cœur complet.


## FINA — feuilles concernées
- ✅ **REMPLIES depuis le socle** (CDF) : F0, F1, F2, F3, F5, F6, F7, F10, F11. (F9 à brancher.)
- 🚫 **NON CONCERNÉES — NE JAMAIS TOUCHER** (listées dans NE_PAS_TOUCHER) : **F4a, F4b, F8, F12**.
  Le générateur ne les modifie pas ; elles restent telles quelles dans le gabarit.
- ✅ **F10 ventilation sectorielle** : taux saisis par secteur (param `ventilation_f10={"commerce":0.81,
  "agricole":0,"services":0.15,"autres":0.04}`) appliqués au total réel. Somme des colonnes = total.
  Contrôle `_F10_somme_taux` (alerte si ≠ 100%).
- Effectifs RH (F2b) via param rh={}.


## Rapport 5 — AML / LBC-FT (août 2026, sur données réelles)
- `engine/aml.py` + `engine/aml_ecriture.py` : extrait opérations espèces (dépôts/retraits par seuil
  10k / 5k-10k USD) des brouillards USD+CDF, et transferts (GL comptes 330/331/332, libellé transfert).
- Règles CDG : dépôt = "Dépôt espèces" + "épargne à la carte" ; retrait = "Retrait en espèces" ;
  CDF converti au taux pour classer par seuil.
- **Résultats août 2026** : dépôts >=10k : 2 ops/30 581 USD ; dépôts 5k-10k : 26/169 560 ;
  retraits 5k-10k : 105/828 730 ; transferts : 734 ops/1 357 615.
- **Taux CDF lu automatiquement** depuis `param_taux_change` à la date de fin de période (§42) —
  plus de taux en dur. Août 2026 : 2263,57 (saisi une fois, utilisé par AML + FINA + indicateurs).
- Fichier rempli : `AML_aout_2026_rempli.xlsx` (section 3 opérations espèces + période).
- Reste : sections par secteur d'activité client (classification à fournir), alertes (saisie),
  taille/portefeuille (depuis socle si balance/crédit du mois chargés).


## Rapport 5 — AML COMPLET (corrigé après retour CDG)
- `engine/aml.py` + `aml_ecriture.py` : remplit TOUTES les lignes calculables du LBC-FT :
  - **1. TAILLE** : Total Opérations (espèces+transferts), Total Opérations espèces (dépôts+retraits),
    Total Dépôts, Total encours crédit (= encours USD × taux), Crédits conso (Staff + Avance salaire).
  - **2. PORTEFEUILLE CLIENT** : statut **1=PP, 2=PM, 4=groupe (INCLUS)**. Solde = **solde_fin**,
  converti par compte (USD→CDF au taux). Total clients = PP+PM+groupes. Août : PP 63 893 (8,95 Mds),
  PM 151 (5,12 Mds), groupes 3 566 (732 M) → total 67 610 clients, 14,8 Mds CDF (≈ épargne bilan 33+34 ✓).
  - **3. Opérations espèces par seuil** (10k / 5k-10k), CDF converti au taux daté.
  - **7. LOCALISATION** : **opérations dépôt+retrait** par province (pas les comptes). Chaque mouvement
  > 0 = 1 op (ligne avec dépôt ET retrait = 2 op). Montants USD→CDF. Août : Kinshasa 9 747 op,
  Haut-Katanga 3 212, Nord-Kivu 192.
- **Inventaire dépôt = source du portefeuille client + localisation** (statut_juridique, agence, solde).
- Params saisis : encours crédit + nb, crédit conso + nb (fournis par CDG), effectifs.
- Août 2026 rempli avec **inventaire août réel** (171 052 lignes, même format 25 col) : `AML_aout_2026_rempli.xlsx`.
  PP 63 893 / PM 3 717. Format inventaire à conserver comme référence.
- ⚠️ LEÇON : ne JAMAIS livrer un rapport partiel en qualifiant de "restant" ce qui est calculable.
  Toujours calculer tout ce que les sources permettent.

## RÈGLE : GRAND LIVRE TOUJOURS EN USD
- Le grand livre (SAGE) est **toujours en USD** (100% des lignes = "Dollar", vérifié).
- ⇒ Tout montant tiré du GL est converti en CDF au taux daté quand le rapport cible est en CDF
  (AML, FINA). Transferts AML : montant = débit(col5) ou crédit(col6), USD → CDF × taux.
- Erreur corrigée : additionner des USD du GL à des CDF (opérations espèces) → total faux.
  Août : transferts 1 357 615 USD = 3 073 057 038 CDF ; total opérations 10 978 754 810 CDF.


## Rapport 4 — Budget / suivi budgétaire ✅ CLÔTURÉ (doctrine figée)
**PRINCIPE D'INTÉGRITÉ** : la plateforme s'en tient à la BALANCE, sans retraitement. Retraitements
éventuels = hors plateforme, sur Excel à partir des exports. La plateforme garantit l'intégrité.

**DEUX RÉALISÉS (figés définitivement)** :
| Réalisé | Définition | Comparé à | Donne |
|---|---|---|---|
| **Mensuel** | cumulé(N) − cumulé(N-1) | budget DU MOIS | **% de réalisation** |
| **Cumulé (a)** | cumulé depuis janvier | budget ANNUEL TOTAL | **% de progression** (consommation du budget annuel) |
| **Cumulé (b)** | cumulé depuis janvier | budget CUMULÉ À DATE (mois écoulés) | **% de réalisation à date** (réalisé vs prévu à ce stade) |

- La balance arrive en cumulé → cumulé direct, mensuel par différence de 2 cumuls (2 balances requises).
- `engine/budget.py::analyse_ecart` produit les 2 niveaux. Charges + produits.
- Réalisé DIRECT depuis la balance via mapping_budget (table DYNAMIQUE éditable, charges+produits).
- Budget NON LINÉAIRE : feuille "CHARGES ET PRODUITS CONSOLIDE" (mois janv-juin=col2-7, juil-déc=9-14).
- Validé en logique (identique aux provisions DGA). Chiffres exacts dès que vraies balances mensuelles chargées.
- ⏳ RESTE (plus tard) : ÉLABORATION du budget (construction prévisions sur base scientifique).

## Rapport Système de Paiement (BCC) — août 2026
- `engine/systeme_paiement.py` : 2 volets.
  - **Comptes actifs/dormants** (fichier compte dormant) : actif = dernière opération dans les
    **6 derniers mois** avant l'arrêté. Ventilé H/F/PM. Août : 7 268 actifs / 52 186 dormants.
  - **Types de transactions** (inventaire dépôt) : Versement (Cash in = dépôts) / Retrait (Cash out),
    en **nombre ET montant**, **par devise SÉPARÉE (PAS de conversion)** — CDF dans colonnes CDF,
    USD dans colonnes USD. ⚠️ Différent de l'AML (qui convertit). 
  - Août : Versement CDF 151 305 040 (669) + USD 4 340 195 (5 156) ; Retrait CDF 179 295 090 (323)
    + USD 4 240 515 (7 003).
- ⚠️ **Colonnes fichier CROISÉES vs en-tête** : l'en-tête dit "Volume|Valeur" mais les données rangent
  Valeur(montant) puis Volume(nombre). On suit les DONNÉES : col2=montant, col3=nombre. À confirmer CDG.
- ⚠️ Inventaire août : colonne "Mois année" en col 9 décale montant_depot→col23, montant_retrait→col24.
- Fichier : `Systeme_paiement_Aout2026_rempli.xlsx`.

## Assemblage plateforme — Tableau de bord multi-pages (EN COURS)
- `bench/Accueil.py` + `bench/pages/` : tableau de bord Streamlit multi-domaines.
  - Accueil : état du socle, derniers imports.
  - 1_Credit : PAR, provisions, migrations, décaissements par agence.
  - 2_Comptabilite_Indicateurs : bilan, résultat, 17 ratios.
  - 3_Epargne : encours, ventilation, épargnants.
- Lancer : `streamlit run bench/Accueil.py`. Doc : docs/LANCER_TABLEAU_DE_BORD.md.
- Registre des chantiers ouverts : docs/RESTE_A_FAIRE.md.
- À étendre : pages Budget, FINA/AML (génération), analyses DGA. Filtres multi-mois.

## Plateforme — Authentification, upload, export, charte (Streamlit enrichi)
- **Authentification & rôles** (`socle/auth.py`, table Utilisateur) : login + mdp haché (sha256+sel).
  Rôles : DIRECTION/CDG (accès total + import), AGENCE (cloisonné à son agence), AUDIT (lecture).
  Comptes démo : admin/admin2026, cdg/cdg2026, victoire/agence2026, audit/audit2026 (à changer en prod).
- **Cloisonnement par agence** : `agences_visibles()` filtre ; un rôle AGENCE ne voit que ses données.
- **Upload** : page Import/Export (réservée DIRECTION/CDG) — charge Excel/CSV du CBS, choix devise/feuille.
- **Export Excel** : bouton de téléchargement sur les pages (openpyxl).
- **Charte MICROPOP** : logo (bench/assets), bleu foncé #0B3D5C (principal), cyan #00AEEA en accent léger, gris #58595B, signature "Je rêve, je réalise".
- Pages : Accueil, Crédit (cloisonné+export), Comptabilité&Indicateurs, Épargne, Import/Export.
- Choix archi : Streamlit enrichi maintenant ; migration Django prévue pour déploiement large.

## Plateforme — pages étendues + démarrage
- Pages ajoutées : **5_Budget** (suivi 3 niveaux + export), **6_Rapports_reglementaires**
  (génération FINA/AML/système paiement depuis l'interface, avec upload gabarit + download).
- **preparer_demo.py** : script tout-en-un (comptes + import démo). Doc : docs/DEMARRAGE_RAPIDE.md.
- Lancement : `python preparer_demo.py` puis `streamlit run bench/Accueil.py`.

## Front Next.js (`web/`) — socle posé
- **Next.js 16 + TypeScript + Tailwind v4 + App Router + `src/`**, `@supabase/ssr`.
  ⚠️ Next 16 : le `middleware` s'appelle **`proxy`** (`src/proxy.ts`, runtime nodejs) et
  `cookies()` / `params` / `searchParams` sont **asynchrones**.
- **Charte** dans `src/app/globals.css` (`@theme` Tailwind v4) : `pop-bleu` #0B3D5C,
  `pop-bleu-2` #1B5E86, `pop-cyan` #00AEEA, `pop-gris` #58595B, `pop-fond` #F4F7FA.
  Le cyan ne tient pas le contraste en aplat (2,48:1) → accents seulement (filets, focus, liens).
- **Écrans** : `/login` (Supabase Auth, logo + « Je rêve, je réalise ») et `/credit`
  (Encours en chiffre phare, PAR1/PAR30/PAR90, provisions, PAR30 par agence en graphique
  + tableau, filtre de date d'arrêté dans l'URL `?arrete=`).
- **Rôle lu côté serveur** dans la table `utilisateur` (via `auth_uid`), jamais dans les
  métadonnées du jeton — même source que `pp_role()` (RLS) et `utilisateur_courant()` (API).
- **Cloisonnement, 3e verrou** : `src/lib/roles.ts` est le miroir exact de
  `api/auth_supabase.py`, et le contexte `ContexteSession.tsx` masque les agrégats
  institution. Un rôle AGENCE ne voit que sa ligne, et son total est la **somme de ses
  seules lignes** (jamais l'agrégat MICROPOP) — vérifié sur les deux rôles.
- **Aucun calcul dans le front** : il appelle `GET /par` et `GET /provisions`. Si l'API ne
  répond pas, l'écran le dit et n'affiche rien plutôt qu'un chiffre estimé.
- **Mode démonstration** (données d'illustration calées sur mai 2026) tant que Supabase
  n'est pas configuré : double verrou — s'éteint dès que `.env.local` est renseigné et
  **impossible en production**. Tout écran ainsi alimenté porte un bandeau explicite.
- ⚠️ Pas de `next/font/google` : le téléchargement de la fonte à la compilation casse
  `build`/`dev` sur un poste sans accès à fonts.gstatic.com → pile de polices système.
- Lancer : `cd web && npm install && cp .env.example .env.local` (remplir les `[A_REMPLIR]`)
  puis `npm run dev`. Doc : `web/README.md`.
- ✅ **Import CBS** : page `/import` (voir la section « Import des fichiers du CBS »).
- Reste : pages compta/indicateurs, épargne, budget, rapports réglementaires,
  export Excel ; puis déploiement Hostinger.

## Import des fichiers du CBS depuis le web (`api/import_cbs.py`)
- **`POST /import/{domaine}`** (multipart) — domaines : `credit`, `balance`, `epargne`,
  `objectifs`, `budget`. N'écrit aucun calcul : le fichier est confié tel quel à
  `ingest/importer_*`. Idempotent (purge du snapshot de la date d'arrêté, règle I-4) ;
  la réponse renvoie `purges` = ce qui vient d'être remplacé.
- **`GET /import/domaines`** : catalogue (extensions, paramètres requis/optionnels). Le
  formulaire du front est CONSTRUIT à partir de cette réponse → une seule liste à tenir,
  côté moteur. **`GET /imports`** : journal (import_log) — ce que la base contient vraiment.
- **Rôles** : `ROLES_ECRITURE = {DIRECTION, CDG}` dans `auth_supabase.py` (miroir de
  `roles.ts`). ⚠️ **L'AUDIT est dans ROLES_ACCES_TOTAL mais PAS dans ROLES_ECRITURE** :
  il lit tout, il n'alimente rien — un contrôleur ne remplit pas ce qu'il contrôle.
- Garde-fous propres au web : nom de fichier assaini (pas de traversée de chemin), taille
  plafonnée (`POPPILOT_IMPORT_MAX_MO`, 200 Mo) écrite **par morceaux**, extension vérifiée,
  **paramètre hors domaine REFUSÉ en 422** (un `devise=CDF` envoyé au crédit serait ignoré
  en silence et l'opérateur croirait avoir chargé du CDF), fichier illisible → **400** (le
  gestionnaire ValueError global de `main.py` en ferait un 404 « arrêté inexistant »),
  `api/.env` au gabarit → **503** plutôt qu'un import atterri dans le SQLite local.
- Endpoint **synchrone** (`def`) : l'ingestion bloque ~15 s pour l'épargne ; en `async def`
  elle figerait la boucle d'événements et l'API entière resterait muette.
- Tests : `python tests/test_import_api.py` — 12 cas (rôles, idempotence, traversée de
  chemin, 400/422/413/503, journal). Inscrits dans `lancer_tous.py`.
- Front : page `/import` (`web/src/app/import/`), réservée DIRECTION/CDG. Le fichier passe
  par le serveur Next (action serveur) → `serverActions.bodySizeLimit: 220mb` dans
  `next.config.ts`, à garder cohérent avec le plafond de l'API. Choix de topologie assumé :
  l'API n'a pas besoin d'être joignable depuis le navigateur.

## Vérification des jetons Supabase — DEUX régimes (ne jamais figer HS256)
- Les projets Supabase récents signent les jetons avec des **clés de signature asymétriques**
  (clé ECC P-256 → **ES256**), vérifiées avec la **clé publique** publiée sur
  `<SUPABASE_URL>/auth/v1/.well-known/jwks.json`. Il n'y a alors **aucun secret partagé**.
- L'ancien régime (**HS256** + `SUPABASE_JWT_SECRET`) reste géré : `api/auth_supabase.py`
  choisit le régime d'après l'algorithme du jeton. Un jeton HS256 est toujours vérifié avec
  le SECRET, jamais avec une clé publique → l'attaque par confusion d'algorithme est fermée.
- ⚠️ `jwt.decode(..., algorithms=["HS256"])` en dur rejette tout jeton d'un projet migré,
  avec « **The specified alg value is not allowed** » — message qui fait croire à un jeton
  corrompu alors que c'est l'API qui regarde au mauvais endroit.
- `api/.env` : **SUPABASE_URL** (URL racine, sans `/rest/v1` ni slash final) est désormais
  requise pour le régime ES256. `cryptography` est requis (PyJWT délègue les courbes
  elliptiques). Les clés publiques sont mises en cache (10 min) : sinon un aller-retour
  réseau par requête.
- L'émetteur (`iss`) est vérifié dès que `SUPABASE_URL` est connue.
- `GET /sante` dit maintenant lequel des deux régimes est actif (`jwt_cles_publiques`,
  `jwt_secret_herite`). Tests : `python tests/test_securite_api.py` — 10 cas, dont
  ES256 accepté, ES256 contrefait rejeté, `alg: none` rejeté.

## Plan d'améliorations (sept. 2026) — modules ajoutés (ADDITIF)
- **Filtres crédit** : `GET /credit/filtre` (api/filtres_credit.py + engine/moteur_filtres). Sans
  filtre = /par au centime. Chargements crédit limités aux colonnes utiles (Supabase : ~60-85 s → s).
- **SAGE** : `POST /sage/traiter` (api/sage.py) — taux JOURNALIER exact de param_taux_change, jour
  sans taux → 422 ; N° pièce/journal/section vides ; Type_Ecriture G ; CG suffixe 0 USD / 1 CDF, 8 chiffres.
- **Imports ajoutés** (domaines de /import) : `compte_resultat_agence` (refus si MICROPOP ≠ Σ agences),
  `taux_change` (Date | Taux ; un taux existant différent n'est écrasé qu'avec remplacer=oui),
  `remboursements` (hiérarchie résolue par n° dossier : encours du mois, puis du mois précédent).
- **Compte d'exploitation agences** : `GET /compte-resultat-agence` (cloisonné par colonne).
- **Productivité** : `GET /productivite` (engine/productivite.py) — intérêts ENCAISSÉS = profitabilité,
  PAS les primes. Roster DU MOIS obligatoire pour les vues agent/superviseur (sinon aucun profil) ;
  hors roster → PORTEFEUILLE ORPHELIN ; agence fermée → PORTEFEUILLE GELÉ.
- **Primes hors AC/SUP** : engine/primes_categories.py sur engine/moteur_primes.py — direction
  (1 % / 0,5 % ; DG 1 %, DGA 0,6 %, DAF 0,3 %, resp. régional 1 %), support (5/10/PAR30), recouvrement
  (1/3/5 % ; resp. 0,3/0,5/1 %), superviseurs épargne (base du palier À CONFIRMER). Objectifs du MOIS seulement.
- **Eljo Smart** : `POST /eljo` (api/eljo.py) — la valeur vient toujours d'un moteur ; mois non importé
  → indisponible (jamais un voisin). Trace eljo_conversation (par login).
- **Archives** : api/archives.py — fichiers dans POPPILOT_ARCHIVES_DIR (hors git) ; remplacer = nouvelle
  version, l'ancienne reste ; édition en ligne = modifications AJOUTÉES (trace), fichier intact ;
  séries (engine/series.py) : calcul_poppilot prime sur import_historique.
- Formats des fichiers à fournir : **docs/FORMATS_FICHIERS.md**.
- ⚠️ Supabase (24/09/2026) : roster/objectifs importés pour MAI seulement ; taux = fins de mois.
