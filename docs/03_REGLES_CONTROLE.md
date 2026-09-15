# Livrable 3 — RÈGLES DE CONTRÔLE DE COHÉRENCE

> Le cahier des tests automatiques. Exécutés **à chaque import** et **avant chaque génération de
> rapport**. Principe : une donnée incohérente est **refusée ou signalée**, jamais absorbée en
> silence (§35, §41). Chaque règle a une **tolérance** distinguant l'arrondi de l'erreur.

**Niveaux de sévérité** :
`BLOQUANT` (refuse l'import/la génération) · `ALERTE` (accepte + signale, exige validation) ·
`INFO` (trace, non bloquant).

---

## 1. CONTRÔLES D'IMPORT (à l'entrée de chaque source)

| # | Règle | Sévérité | Réf |
|---|---|---|---|
| I-1 | Format réel détecté par signature (pas l'extension : `.xls` peut être `.xlsx`) | BLOQUANT | §25.5 |
| I-2 | Colonnes attendues présentes (schéma du domaine) | BLOQUANT | §4.1 |
| I-3 | Date de snapshot **explicite** (jamais TODAY()) ; refus si absente | BLOQUANT | §23 |
| I-4 | Idempotence : ré-import d'une date **remplace** le snapshot, sans doublon | BLOQUANT | §23 |
| I-5 | Import dans le désordre accepté (12 après 14) | INFO | §23 |
| I-6 | Types/domaines valides : dates cohérentes, montants numériques, agence/agent connus | ALERTE | §10 |
| I-7 | Décimales : virgule → point ; séparateur `;` ; BOM UTF-8 (inventaire dépôt) | BLOQUANT | §51 |
| I-8 | Lignes « Total » du fichier remboursé **ignorées** (recalcul depuis détail) | BLOQUANT | §25.3 |
| I-9 | Journalisation : date, fichier, lignes acceptées/rejetées, motif | INFO | §10 |

## 2. CONTRÔLES COMPTABLES (fichier magique, §41)

| # | Règle | Tolérance | Sévérité |
|---|---|---|---|
| C-1 | Balance équilibrée : Σ débit = Σ crédit | ABS < 1 | BLOQUANT |
| C-2 | Bilan équilibré : Actif = Passif | ABS < 1 | BLOQUANT |
| C-3 | Résultat cohérent : Résultat CR = Résultat Bilan (cl.13) | ABS < 1 | BLOQUANT |
| C-4 | Comptes non mappés = 0 (sinon lister) | = 0 | ALERTE |
| C-5 | Fonds propres ≥ 0 | ≥ 0 | ALERTE |
| C-6 | Écart brut débit-crédit **tracé et expliqué** (pas masqué) | — | INFO |

## 3. COHÉRENCES INTER-SOURCES / INTER-RAPPORTS (le cœur — §35)

| # | Règle | Tolérance | Sévérité |
|---|---|---|---|
| X-1 | **Encours crédit unique** : `fait_credit` Σ encours = balance (31+32+39) | ± arrondi (à caler) | BLOQUANT |
| X-2 | FINA : F0(31+32+39) = F5 total = F10 total = F11 encours brut | ABS < seuil | BLOQUANT |
| X-3 | FINA : F0 (39) ≈ F11 total retard | ± 1 000 CDF (arrondi) | ALERTE |
| X-4 | Résultat net : F1 = F0 passif (13) = définition unique du catalogue | ABS < 1 | BLOQUANT |
| X-5 | PAR agent identique partout (Rapport 1 = primes = réglementaire) | exact | BLOQUANT |
| X-6 | Épargne : F0 passif (33)+(34) cohérent avec `fait_epargne` agrégé | ± arrondi | ALERTE |
| X-7 | Ventilation groupe : F5 col. Groupe = crédits LISANGA ; F6 = comptes 331141+33402 | ± arrondi | ALERTE |
| X-8 | Encours USD × taux clôture = encours CDF du FINA | ± arrondi conversion | ALERTE |

> **X-1 et X-5 sont les invariants fondateurs** : ils rendent les rapports cohérents *par
> construction*. Un échec X-1 = données inutilisables. Un échec X-5 = prime potentiellement fausse.

## 4. CONTRÔLES D'HISTORISATION & PARAMÈTRES

| # | Règle | Sévérité |
|---|---|---|
| H-1 | Date de valorisation demandée sans snapshot exact → **signalée** (date effective affichée), jamais interpolée | ALERTE (§20.2) |
| H-2 | Paramètre (roster/objectif/barème/taux) manquant à la date d'effet requise → refus | BLOQUANT (§18.4) |
| H-3 | Calcul rétroactif : utilise les paramètres **de la période cible**, pas d'aujourd'hui | BLOQUANT (§18.4) |
| H-4 | Trou d'historique dans une série (mois manquant) signalé au calcul de moyenne | ALERTE (§29-7) |

## 5. CONTRÔLES DE RATTACHEMENT

| # | Règle | Sévérité |
|---|---|---|
| R-1 | **Orphelin agent** : agent hors roster → Portefeuille Orphelin (par agence du SIG) | ALERTE (§18.2) |
| R-2 | **Orphelin superviseur** : superviseur hors roster → isolé par agence | ALERTE (§18.2) |
| R-3 | **Orphelin décaissement** : décaissement sans agent actif → isolé | ALERTE (§15.3) |
| R-4 | Remboursement non rattachable (cascade RBA→encours→orphelin) | ALERTE (§25.4) |
| R-5 | Affichage explicite des dates par bloc (flux vs provision vs stock décorrélés) | INFO (§21.2) |

## 6. CONTRÔLES DE COHÉRENCE MÉTIER (garde-fous)

| # | Règle | Sévérité |
|---|---|---|
| M-1 | %PAR ∈ [0 ; 100 %] ; alerte si > seuil réglementaire | INFO |
| M-2 | Somme des tranches d'ancienneté ≤ encours retard | ALERTE |
| M-3 | Coût du risque négatif = reprise (normal), pas une erreur | INFO (§21.2) |
| M-4 | Nb clients (Σ AK) ≤ nb crédits (§15.2) | ALERTE |
| M-5 | Objectif proratisé : cumulatif oui, seuil (PAR) jamais | BLOQUANT logique (§24.2) |

---

## PRINCIPE D'IMPLÉMENTATION
Chaque règle = une fonction testable renvoyant `{statut, valeur, écart, message}`. Le **tableau de bord
de contrôle** (inspiré de la feuille CONTROLES du fichier magique, §41) affiche l'état de toutes les
règles avant qu'un rapport soit produit. **Aucun rapport réglementaire n'est généré si un contrôle
BLOQUANT échoue.**
