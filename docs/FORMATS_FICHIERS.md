# Formats des fichiers mensuels à fournir à PopPilot

Règle commune : **ligne 1 = en-têtes**, une ligne par élément, pas de cellules fusionnées.
Montants en nombres (la virgule décimale est acceptée). Les noms d'agence, de superviseur et
d'agent doivent être **écrits exactement comme dans l'extraction crédit du CBS**.

---

## 1. Roster + objectifs (fichier OBJECTIF) — page Import, domaine « objectifs »
Feuille nommée **OBJECTIF**. Date d'effet = **1er du mois** concerné (il ne vaut que pour ce mois).

| Col. | En-tête | Contenu | Exemple |
|---|---|---|---|
| A | AGENCE | nom CBS de l'agence | AGENCE OZONE |
| B | SUPERVISEUR | nom CBS complet du superviseur | MBOLELA KANDA  RODDY |
| C | AGENT DE CREDIT | nom CBS complet de l'agent | SABWA TSHIBANGU PATRICK |
| D | #NOMBRE A DECAISSE | objectif en nombre de crédits | 10 |
| E | VOLUME | objectif de décaissement (USD) | 70000 |
| F | PORTEFEUILLE (volume Encours) | objectif d'encours (USD) | 250000 |
| G | PORTEFEUILLE (Nombre de client) | objectif de clients | 100 |
| H | PAR | objectif de PAR, en fraction | 0,05 (= 5 %) |

⚠️ **Noms** : dans le fichier de mai, les 9 superviseurs sont en nom court (« KANDA RODDY »)
alors que l'encours porte le nom complet (« MBOLELA KANDA  RODDY ») → aucun ne correspond, ils
passeraient en orphelins. Copier les noms depuis l'extraction crédit.
⚠️ **Complétude** : tout agent actif absent du fichier passe en « portefeuille orphelin »
(mai : 70 noms d'agents de l'encours absents du fichier, 2,14 M USD — dont le portefeuille
gelé de Goma, agence fermée, qui n'est pas un orphelin). Inclure tous les agents actifs,
même sans objectif (laisser D-H vides).

## 2. Taux de change journaliers — page Import, domaine « taux_change »
Première feuille, deux colonnes : **Date | Taux** (USD→CDF), un taux par jour.
Une date déjà en base avec un autre taux bloque l'import (elle sert au FINA/AML) : écrire
« oui » dans « Remplacer » pour l'écraser volontairement.

## 3. Crédits remboursés — page Import, domaine « remboursements »
Export CBS tel quel (feuille Worksheet, 9 colonnes : Date | N° échéance | N° client | Noms |
N° dossier | Montant déboursé | Capital | Intérêts | Pénalités). Importer d'abord l'encours
du même arrêté. Sert la productivité (pas les primes).

## 4. Compte de résultat par agence — page Import, domaine « compte_resultat_agence »
Fichier COMPTE_RESULTAT_<mois>_isolé.xlsx, feuille **Feuil2** : A = poste, B→G = Victoire,
Ozone, Goma, Lubumbashi, Masina, Gombe, H = MICROPOP. Refusé si MICROPOP ≠ somme des agences.

## 5. Recouvrement — page Primes
**Équipe | Agent | Agence | Montant 91-180 | Montant 181+ | Montant Radié**, puis une ligne
TOTAL (contrôle : la somme des agents doit la redonner).

## 6. Épargne des superviseurs — page Primes
**Agence | Cible | Réalisation | %**, puis une ligne TOTAL (contrôle). Le % est recalculé.

## 7. Historiques d'indicateurs — page Archives, onglet Séries
**Indicateur | Date | Agence | Valeur | Unité** (Agence vide = consolidé MICROPOP).
Indicateurs reconnus : encours_credit, par1, par30, par90, pct_par30, nb_credits, provisions,
epargne (tout autre nom est accepté comme nouvelle série).
