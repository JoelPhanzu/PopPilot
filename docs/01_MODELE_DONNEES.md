# Livrable 1 — MODÈLE DE DONNÉES DU SOCLE

> Le plan des fondations. Répond à : **quels faits bruts stocke-t-on, et comment sont-ils reliés ?**
> Principe directeur (CLAUDE.md §0.1) : le socle **stocke des faits datés**, il **ne stocke jamais**
> d'indicateur calculé. Tout KPI (Livrable 2) se calcule par-dessus. Ajouter un domaine = ajouter une
> table de faits + ses calculs, sans toucher à l'existant.

---

## A. Principes transversaux (valent pour toutes les tables)

1. **Historisation par snapshot daté** — chaque import est un instantané horodaté, jamais écrasé
   (§16, §20). **Deux dates distinctes et NON confondues** (§69.2) :
   - `date_snapshot` : quand la photo est prise / l'import est fait (ex. 4 mai).
   - `date_arrete` (**= date comptable, fait foi**) : dernier jour ouvré du mois que porte la donnée
     (ex. 30 avril). Le SIG fige le temps au dernier jour ouvré ; la clôture réelle tombe souvent le
     3-5 du mois suivant. **Rattachement de période, cohérences et moyennes se calculent sur `date_arrete`.**
   - `periode` : mois/exercice métier (déduit de `date_arrete`).
2. **Devise** — montants stockés dans leur **devise d'origine** (`USD` ou `CDF`) + une table de
   **taux de clôture datés** ; toute conversion est **dérivée**, jamais stockée (§42).
3. **Ne stocker que le brut** — pour le crédit, colonnes SIG **A→AF uniquement** ; les colonnes
   dérivées (provisions, migrations, projections) sont recalculées (§4.2, §6).
4. **Clé pivot universelle** — `numero_dossier` relie crédit ↔ remboursements ↔ FINA (§25.4).
5. **Paramètres versionnés à date d'effet** — roster, objectifs, barème, taux, normes, plan de
   comptes, mappings : un calcul sur une période passée utilise les paramètres **de l'époque** (§18.4).
6. **Grain = ligne source** — une ligne de prêt, un compte d'épargne, une écriture, une transaction.
   L'agrégation (agent → superviseur → agence → filiale) est un **calcul**, pas un stockage (§5).

---

## B. DOMAINES ET TABLES DE FAITS

### Domaine 1 — CRÉDIT

**`fait_credit`** (grain : un prêt actif à une date de snapshot ; source : extraction SIG A→AF, §4.1)

| Champ | Type | Notes |
|---|---|---|
| date_snapshot | date | **PK composite** avec numero_dossier |
| numero_dossier | entier | **clé pivot universelle** |
| numero_client | entier | |
| nom_client | texte | donnée perso → anonymisable en dev |
| produit_credit | texte | **`est_groupe = (produit == 'LISANGA')`** (§45) |
| agence | texte | rattachement |
| agent_credit | texte | clé roster (§ contrôle orphelin) |
| superviseur | texte | |
| id_groupe, nom_groupe | | prêts de groupe |
| sexe (Femme/Homme) | 0/1 | |
| montant_debourse | nombre | devise d'origine |
| date_deboursement | date | → derive: année/mois/jour (filtres décaissement) |
| date_fin_echeance | date | |
| duree, taux_interet, frequence | | |
| **encours** | nombre | base encours + PAR |
| interets, interets_retard, penalites | nombre | |
| **jours_de_retard** | entier | base PAR + ancienneté |
| capital_retard, impayes, garantie | nombre | |
| tranche_1_7 … tranche_361plus | nombre | 7 tranches d'ancienneté (montants) |
| devise | USD/CDF | |

**`fait_remboursement_attendu`** (grain : une échéance due sur une période ; source RBA, §25.1)
`date_snapshot, numero_dossier, numero_client, date_echeance, capital_attendu, interet,
capital_restant, produit_credit, agent, superviseur, agence, devise`

**`fait_remboursement_realise`** (grain : une ligne d'échéance encaissée ; source CRB, §25.2)
`date_snapshot, numero_dossier, numero_echeance, date_remboursement, numero_client,
capital_rembourse, interets_rembourses, penalites_rembourses`
> ⚠️ **Ignorer les lignes « Total » du fichier** (troncature, §25.3) → recalcul depuis le détail.
> Agent/agence **absents** → rattachement en cascade par numero_dossier (§25.4).

### Domaine 2 — ÉPARGNE

**`fait_epargne`** (grain : un compte de dépôt à une date ; source inventaire dépôt, §51)

| Champ | Notes |
|---|---|
| date_snapshot | |
| id_compte, num_complet_cpte, id_client | |
| id_prod, libelle_produit | → mapping type (voir dimension) |
| agence (libelle_niveau), devise | |
| solde_actuel, solde_debut, solde_fin | **stock** |
| montant_depot, montant_retrait | **flux** |
| sexe, secteur_activite, ville, date_ouverture | |
| **est_groupe** | Transitoire Groupe (id 15/17) + Caution Groupes (id 20) → comptes 331141 / 33402 (§51.3) |
| **type_depot** | à vue / à terme (DAT id 10/21) / obligatoire (Nantie, Caution) (§51.4) |

### Domaine 3 — COMPTABILITÉ

**`fait_balance`** (grain : un compte × arrêté ; source balance USD → fichier magique, §38)
`date_arrete, numero_compte, libelle, debit_initial, credit_initial, debit_mvmt, credit_mvmt,
solde_net (devise origine), devise`
> Le **fichier magique** (mapping préfixe→agrégat, §40) transforme cette table en bilan/CR normalisés.

**`fait_grand_livre`** (grain : une écriture ; source GL, §55, §62)
`date_ecriture, numero_compte, ligne_budgetaire, mois, libelle, devise, montant`

### Domaine 4 — TRANSACTIONS / TRÉSORERIE

**`fait_transaction_caisse`** (grain : une opération de caisse ; source brouillard USD+CDF, §54)
`date_heure, guichet, agent, numero_transaction, libelle_operation, numero_client, nom_client,
montant_debite, montant_credite, encaisse, devise`
> Catégorisation via **mapping libellé → catégorie** (§54.1) : dépôt espèces = « Dépôt espèces » +
> « Dépôt épargne à la carte » ; retrait = « Retrait en espèces » ; transferts via GL (330/331/332).

### Domaine 5 — BUDGET (saisie humaine, pas SIG)

**`fait_budget`** (grain : ligne budgétaire × agence × mois × hypothèse ; source budget, §46)
`exercice, hypothese (H1/H2…), agence, ligne_budgetaire, produit, mois, montant_budgete, type
(encours/produit/charge/effectif/PAR_cible…)`
> Seule table **alimentée par saisie/versionnement** via l'outil, pas par import SIG (§46).

### Domaine 6 — RÉMUNÉRATION (rattaché RH)

**`fait_prime`** (grain : employé × période ; dérivé des KPI + barème, §60)
`periode, employe, fonction, agence, base_volume, base_nombre, base_couverture, par_agent,
correcteur_par, prime_calculee` — le correcteur PAR et le barème viennent des **paramètres** (§60).

---

## C. TABLES DE DIMENSIONS (référentiels)

| Table | Contenu | Source |
|---|---|---|
| **dim_agence** | code, nom, région, date ouverture | roster |
| **dim_employe** (roster) | agent/superviseur, agence, fonction, **date_debut/date_fin** | Composition Equipe (§5), RH |
| **dim_produit_credit** | produit, est_groupe, secteur (Commerce/Agricole/Services/Autres) | §10 (F10) |
| **dim_produit_epargne** | id_prod, libellé, type_depot, est_groupe, compte BCC | inventaire (§51) |
| **dim_plan_comptable** | numéro, libellé, préfixe, agrégat | plan BCC (§27, §40) |
| **dim_client** | numéro, nom, sexe, secteur, ville, statut juridique | crédit + épargne |

---

## D. TABLES DE PARAMÈTRES (versionnées à date d'effet — §18.4)

| Table | Contenu | Réf. |
|---|---|---|
| **param_bareme_provision** | tranche → taux (5/25/50/75/100 %) → code 0-6 | §4.4 |
| **param_objectif** | agence/agent × période → décaissement, volume, portefeuille, PAR cible | §15.3 |
| **param_taux_change** | date → taux clôture USD/CDF | §42 |
| **param_bareme_prime** | primes (volume/nombre/couverture), seuils, **correcteur PAR** | §60 |
| **param_mapping_compte** | préfixe/compte → {destination, rubrique, type IMF, agrégat} | §40 |
| **param_mapping_libelle** | libellé opération → catégorie (dépôt/retrait/transfert) | §54.1 |
| **param_norme_bcc** | indicateur → norme, seuil, constante (capital min 700 000 $…) | §28 |
| **param_instruction_bcc** | règles d'annualisation, positions de change | §57 |
| **param_calendrier_ouvre** | jours ouvrés RDC (fériés + exceptions) → prorata & dernier jour ouvré | §69 |
| **param_reintegration** | par nature de charge → taux de réintégration fiscale (comm. 50 %, dons perso 100 %…) | §67 |
| **param_taux_ibp** | taux légal IBP = 30 %, appliqué au **résultat fiscal** à l'arrêté annuel | §67 |
| **param_mapping_fina** | compte/agrégat → case FINA (V1.F…) | §37 |

---

## E. SCHÉMA DE LIAISON (comment tout se relie)

```
                          param_* (datés)   dim_* (référentiels)
                                 │                  │
   fait_credit ──numero_dossier──┼── fait_remboursement_attendu / _realise
        │                        │
        │  (encours partagé)     ├── fait_epargne ──┐
        ▼                        │                  │
   fichier magique ◄── fait_balance ── fait_grand_livre
        │                                           │
        ▼                                           ▼
   BILAN / CR normalisés ───► indicateurs, FINA, budget vs réalisé
                                                    │
   fait_transaction_caisse ────────────────────────┴── AML, stats opérations
   fait_budget ──(vs réalisé)── analyse d'écart ── primes (correcteur PAR)
```

**Invariant central** : l'**encours crédit** est calculé **une seule fois** depuis `fait_credit` et
doit coïncider avec `fait_balance` (comptes 31+32+39). Cette égalité, vérifiée par le Livrable 3,
rend cohérents Rapport 1, Rapport 2, FINA et primes **par construction** (§35, §44).
