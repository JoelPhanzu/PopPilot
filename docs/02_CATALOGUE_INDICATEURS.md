# Livrable 2 — CATALOGUE UNIFIÉ DES INDICATEURS

> Le dictionnaire officiel. Chaque indicateur est défini **une seule fois** : id, formule exacte,
> source, maille, nature. Tout rapport **référence** une entrée du catalogue — jamais une redéfinition.
> **Nature** (§19, §21) : `STOCK` (lu à une date) · `FLUX_EVT` (sommé sur intervalle) ·
> `FLUX_DIFF` (différence de deux stocks entre deux dates) · `RATIO` · `PARAM/SAISIE`.

**Maille standard** : tout indicateur d'activité est décliné AGENT › SUPERVISEUR › AGENCE › GLOBAL.
Les ratios sont **recalculés à chaque niveau** (jamais sommés).

---

## CATÉGORIE A — PORTEFEUILLE & RISQUE (source : `fait_credit`)

| ID | Indicateur | Formule | Nature | Réf |
|---|---|---|---|---|
| CR-ENC | Encours crédit | Σ `encours` | STOCK | §7.4 |
| CR-PAR1 | PAR 1 | Σ `encours` où `jours_retard > 0` | STOCK | §7.1 |
| CR-PAR30 | PAR 30 | Σ `encours` où `jours_retard > 30` | STOCK | §7.1 |
| CR-PAR90 | PAR 90 | Σ `encours` où `jours_retard > 90` | STOCK | §7.1 |
| CR-PPAR30 | % PAR 30 | CR-PAR30 ÷ CR-ENC | RATIO | §7.1 |
| CR-CROIS | Croissance portefeuille | (CR-ENC ÷ CR-ENC[M-1]) − 1 | FLUX_DIFF | §7.4 |
| CR-NBCLI | Nombre de clients | Σ `AK` (=1/nb crédits du client) | STOCK | §15.2 |
| CR-NBCRE | Nombre de crédits | comptage lignes (`AJ`) | STOCK | §15.2 |

> ⚠️ AJ = nb crédits, AK = nb clients (§15.2). Numérateur PAR = **encours total** du prêt, seuils **stricts**.

## CATÉGORIE B — PROVISIONS & COÛT DU RISQUE (dérivé §6, filtre PROVISION §21.2)

| ID | Indicateur | Formule | Nature | Réf |
|---|---|---|---|---|
| PV-TAUX | Taux de provision | barème(jours_retard) : 0/5/25/50/75/100 % | PARAM | §4.4 |
| PV-CAP | Provision capital | `encours × taux` (**seule retenue**, BCC) | STOCK | §6 |
| PV-CR | Coût du risque | Σ (prov capital[date_val] − prov capital[date_réf]) | FLUX_DIFF | §7.2 |
| PV-CRPROJ | Potentiel CR fin de mois | Σ `CR projeté` | FLUX_DIFF | §7.2 |
| MIG-ENTREE | Entrée en PAR (#/montant) | prêts état=Migration, code 0 | FLUX_DIFF | §7.6 |
| MIG-VERS | Migration vers tranche X | Σ encours Migration code 1..5 | FLUX_DIFF | §7.6 |
| REC-RECUP | Récupération (# / montant) | prêts état=Récupération (code M < M-1) | FLUX_DIFF | §7.2bis, §14 |

> **REC-RECUP** : calculé mais jamais exploité aujourd'hui → gisement (§14). Pendant positif du PAR.

## CATÉGORIE C — DÉCAISSEMENT & PRODUCTIVITÉ (source `fait_credit`, filtre FLUX §21.2)

| ID | Indicateur | Formule | Nature | Réf |
|---|---|---|---|---|
| DEC-NB | Nombre décaissé | # prêts déboursés sur [début;fin] | FLUX_EVT | §7.3 |
| DEC-VOL | Volume décaissé | Σ `montant_debourse` sur [début;fin] | FLUX_EVT | §7.3 |
| DEC-P15 | #P15 | # déboursés jour ≤ 15 | FLUX_EVT | §7.3 |
| DEC-REAL-N | % réalisation nombre | DEC-NB ÷ objectif nombre (proratisé) | RATIO | §24.2 |
| DEC-REAL-V | % réalisation volume | DEC-VOL ÷ objectif volume (proratisé) | RATIO | §24.2 |
| DEC-PROD | Productivité | DEC-NB ÷ effectif agents actifs | RATIO | §7.5 |
| REC-TAUX | Taux de recouvrement | réalisé (CRB) ÷ attendu (RBA) | RATIO | §25 |

> Objectifs **cumulatifs** proratisés `× (jours écoulés / jours mois)` ; objectifs **seuils** (PAR) jamais (§24.2).

## CATÉGORIE D — INDICATEURS DE PERFORMANCE & RATIOS PRUDENTIELS (source balance via fichier magique, §28)

| ID | Indicateur | Formule | Norme | Réf |
|---|---|---|---|---|
| IP-A1 | PAR 30 (réglementaire) | capital restant dû >30j ÷ portefeuille brut | < 5 % | §28 A.1 |
| IP-A2 | Abandon de créances | radiés (≥361j au 31/12) ÷ portef. brut moyen | < 2 % | §28 A.2 |
| IP-B1 | Efficacité opérationnelle | charges expl. ÷ encours moyen | 13-21 % | §28 B.1 |
| IP-B2 | Emprunteurs / agent | emprunteurs actifs ÷ agents (**sans ×100**) | > 130 | §28 B.2 |
| IP-C1 | ROE | résultat net ÷ fonds propres moyens | > 15 % | §28 C.1 |
| IP-C2 | ROA | résultat net ÷ actif moyen | > 3 % | §28 C.2 |
| IP-C3 | Rendement du portefeuille | (712x+715x+717x) ÷ encours moyen | > 15 % | §28 C.3 |
| IP-C4 | Autosuffisance opérationnelle | Σ classe 7 ÷ Σ classe 6 | > 119,2 % | §28 C.4 |
| IP-D1 | Encaisse oisive | disponibles (56+57) ÷ total actif | < 20 % | §28 D.1 |
| IP-D2 | Taux d'encours de crédit | portefeuille brut ÷ total actif | > 70 % | §28 D.2 |
| IP-D3 | Taux des immobilisations | immob. nettes ÷ total actif | < 10 % | §28 D.3 |
| IP-E1 | Capital minimum | fonds propres base ÷ 700 000 $ | ≥ 100 % | §28 E.1 |
| IP-E2 | Solvabilité | fonds propres prudentiels ÷ **total actif période** (pas de RWA, §68) | ≥ 10 % | §28 E.2 |
| IP-E3 | Capitalisation | fonds propres base ÷ total actif | ≥ 15 % | §28 E.3 |
| IP-E4 | Liquidité immédiate | disponibilités ÷ dépôts à vue | ≥ 20 % | §28 E.4 |
| IP-E5 | Couverture immob. par FPP | immob. nettes ÷ fonds propres prudentiels | ≤ 50 % | §28 E.5 |
| IP-E6 | Couverture emplois MLT | ressources stables ÷ emplois stables | ≥ 100 % | §28 E.6 |

**RÉSULTAT NET (défini une fois, §67 — corrigé)** : `résultat comptable = Produits − Charges` ;
`résultat fiscal = comptable + Σ(charge×taux_réintégration)` ; `IBP = fiscal × 30 %` ;
`résultat net = comptable − IBP`. Impôt **à l'arrêté annuel seulement**. Taux effectif variable
(≈77 % du résultat comptable en 2025) → **jamais figer un taux** ; grille de réintégration paramétrable.

> **Moyennes de période** = moyenne des soldes datés (§29-7, pas la moyenne à 2 points). Flux
> (B1, C1-C4) **annualisés explicitement** (§29-3). Résultat net : **définition unique** à trancher (§29-1).
> ⚠️ Points de doctrine ouverts §29 : résultat net unique, dénominateur solvabilité (actif vs RWA), périmètre dépôts à vue.

## CATÉGORIE E — ÉPARGNE (source `fait_epargne`)

| ID | Indicateur | Formule | Nature | Réf |
|---|---|---|---|---|
| EP-ENC | Encours épargne | Σ `solde_actuel` | STOCK | §51 |
| EP-DAV | Dépôts à vue | Σ soldes type=à vue (hors DAT & obligatoire) | STOCK | §51.4 |
| EP-DAT | Dépôts à terme | Σ soldes type=à terme | STOCK | §51.4 |
| EP-NBEP | Nombre d'épargnants | comptes/clients uniques | STOCK | §34 |
| EP-RATIO | Ratio crédit/épargne | CR-ENC ÷ EP-ENC | RATIO | §Rapport1 |
| EP-DEP/RET | Dépôts / retraits (flux) | Σ montant_depot / montant_retrait sur période | FLUX_EVT | §51.1 |

## CATÉGORIE F — BUDGET & ÉCARTS (source `fait_budget` vs réalisé)

| ID | Indicateur | Formule | Réf |
|---|---|---|---|
| BU-ECART | Écart (valeur) | réalisé − budgété (par ligne × mois, mensuel & cumulé) | §61 |
| BU-REAL | % réalisation | réalisé ÷ budgété | §61 |
| BU-VOLPRIX | Décomposition volume/prix | effet-volume + effet-prix (bridge, §22) | §50 |

## CATÉGORIE G — TRANSACTIONS / AML (source `fait_transaction_caisse`, `fait_grand_livre`)

| ID | Indicateur | Formule | Réf |
|---|---|---|---|
| TX-DEPOT | Dépôts espèces (# / valeur) | libellés « Dépôt espèces » + « Dépôt épargne à la carte » | §54.1 |
| TX-RETRAIT | Retraits espèces (# / valeur) | libellé « Retrait en espèces » | §54.1 |
| TX-TRANSF | Transferts entre comptes | GL comptes 330/331/332, libellé transfert | §53 |

## CATÉGORIE H — PORTÉE & RÉMUNÉRATION

| ID | Indicateur | Formule | Réf |
|---|---|---|---|
| PO-EMP | Nb employés / agents crédit | RH (saisie) | §34 |
| RH-PRIME | Prime employé | base × correcteur PAR (×1/0,7/0,5/0) selon PAR agent | §60 |

> **RH-PRIME** dépend de CR-PAR30 par agent → illustre la **source unique** : un seul PAR pour reporting,
> réglementaire et paie.

## ADDITIONS DU 25/09/2026 (décisions CDG) — tableaux de bord crédit et épargne

| ID | Indicateur | Formule | Type | Source |
|---|---|---|---|---|
| CR-NBCLI | Nombre de clients | **noms de clients distincts** (casse / espaces ignorés) de la ligne | STOCK | règle CDG 25/09 |
| CR-NBCRED | Nombre de crédits | dossiers (numero_dossier) de la ligne | STOCK | règle CDG 25/09 |
| CR-POTCR | Potentiel coût du risque fin de mois | coût du risque (prêt par prêt vs M-1) recalculé sur les prêts PROJETÉS au dernier jour du mois sans aucun recouvrement : retard > 0 → retard + jours restants ; retard 0 dont une échéance tombe avant la fin du mois → jours depuis l'échéance | PROJECTION | engine/potentiel.py |
| CR-POTMIG | Potentiel migration | crédits SAINS (retard 0) à l'arrêté qui seraient en retard au dernier jour du mois (nb, encours) | PROJECTION | engine/potentiel.py |
| CR-ENCAIS | Intérêts / capital / pénalités encaissés | Σ fichier « Crédits remboursés » dont la date tombe dans [début ; fin] | FLUX | fait_remboursement_encaisse |
| CR-RECPAR | Recouvré sur PAR | encaissements (capital + intérêts + pénalités) sur les dossiers en retard à l'arrêté M-1 | FLUX | idem |
| CR-TOPN | Top N meilleurs / pires clients | meilleurs : clients sans retard, triés par encours, décaissé (période) ou nb de crédits ; pires : encours en retard du client | CLASSEMENT | engine/moteur_classement_clients.py |
| EP-COLNET | Collecte nette | dépôts − retraits des inventaires de la période (mois entiers, chaque mois à son taux) | FLUX | engine/tableau_de_bord_epargne.py |
| EP-COUV | Couverture du crédit | épargne (USD) ÷ encours crédit, même agence, même arrêté | RATIO | idem ; critère primes support ≥ 60 % |
| RH-PRIME-SUPEP | Prime superviseurs épargne | palier sur la réalisation TOTALE du mois (≥ 50 k → 60 ; ≥ 70 k → 100 ; ≥ 100 k → 200 USD) | PRIME | fait_collecte_epargne |

> Échéances (CR-POTMIG) : le CBS ne donne pas la prochaine échéance ; elle est déduite de la date de
> déboursement et de la fréquence (« Mensuelle » : même quantième ; « Tous les 28 jours » : pas de 28 j).

## ADDITION DU 25/09/2026 — variation de provision (demande CDG)

| ID | Indicateur | Formule | Type | Source |
|---|---|---|---|---|
| PV-VAR | Variation de provision (provision constituée sur le mois) | provisions à date (barème + complément DAF) − provisions de la fin du mois précédent (barème et complément DAF en vigueur à M-1) | FLUX_DIFF | engine/tableau_de_bord_credit.py |

> PV-VAR ≠ PV-CR : la variation porte sur les **totaux** (inclut prêts nouveaux, soldés, radiés) ;
> le coût du risque est le différentiel **prêt par prêt** sur le portefeuille présent aux deux dates.
> Les deux sont affichés. Juin / juillet / août 2026 : 44 208,13 / 39 553,12 / 48 010,02.
