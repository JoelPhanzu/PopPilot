# Livrable 4 — BACKLOG DE CONSTRUCTION PRIORISÉ

> L'ordre de chantier. Pas « tout ce qu'il faut faire » mais **par quoi commencer et pourquoi**.
> Principe : livrer vite une brique **testable sur données réelles**, validée contre l'Excel existant,
> puis empiler. Chaque lot produit quelque chose de vérifiable — jamais un big-bang.

**Règle d'or de validation** : chaque indicateur recodé est **rapproché du fichier Excel du même mois**
(tolérance d'arrondi). Tant que le chiffre ne tombe pas juste, on ne passe pas à la suite.

---

## PHASE 0 — Fondations techniques (avant tout calcul)
| Lot | Contenu | Sortie testable |
|---|---|---|
| 0.1 | Dépôt, structure `engine/ ingest/ tests/ bench/`, `CLAUDE.md` + 4 livrables à la racine | squelette qui tourne |
| 0.2 | Base de données du socle (schéma Livrable 1) : tables de faits, dimensions, paramètres datés | migrations créées |
| 0.3 | Socle d'historisation : snapshot daté, idempotence, import dans le désordre (§23) | 1 snapshot importé/relu |

## PHASE 1 — Crédit : le cœur, validé contre le Daily Tool ⭐ PRIORITÉ
> On commence par le crédit car c'est le domaine le plus complet, le plus utilisé, et celui qui
> alimente le plus d'autres rapports (FINA, primes, budget).

| Lot | Contenu | Validation |
|---|---|---|
| 1.1 | Import `fait_credit` (A→AF) + validations I-1..I-9 | charge l'extraction de mai |
| 1.2 | Étage de dérivation (§6) : barème provision, provision capital, codes tranche | prov. capital = Excel |
| 1.3 | **PAR1/30/90 + %PAR** (catalogue CR-*) aux 4 niveaux | **PAR mai = Dashboard mai** |
| 1.4 | Rapprochement M/M-1 générique → coût du risque, migrations, récupération | Variation = Excel |
| 1.5 | Décaissement avec **filtre date début/fin** (§18.1) + productivité | volume/nb = Excel |
| 1.6 | Orphelins agent + superviseur par agence (R-1..R-3) | liste orphelins cohérente |
| 1.7 | Banc d'essai Streamlit : dashboard crédit complet | reproductible à l'écran |

**→ Jalon 1 : le Rapport 1 tourne en local sur données réelles, chiffres validés.**

## PHASE 2 — Comptabilité : le fichier magique en Python
> Deuxième priorité car il débloque Rapports 2, 3 et le budget d'un coup.

| Lot | Contenu | Validation |
|---|---|---|
| 2.1 | Import `fait_balance` + `param_mapping_compte` (préfixe→agrégat, §40) | comptes tous mappés (C-4) |
| 2.2 | Moteur bilan/CR normalisés BCC + conversion USD→CDF datée (§42) | bilan = fichier magique |
| 2.3 | Contrôles comptables C-1..C-6 (équilibre, résultat, écart tracé) | contrôles verts |
| 2.4 | Import `fait_grand_livre` (charges réelles multi-mois) | GL chargé |

**→ Jalon 2 : états financiers reproduits et contrôlés.**

## PHASE 3 — Reporting réglementaire & de gestion (vues du socle)
| Lot | Contenu | Validation |
|---|---|---|
| 3.1 | **Rapport 2** — 17 indicateurs & ratios prudentiels (IP-*), moyennes datées, annualisation | résultats = note explicative |
| 3.2 | Cohérences inter-rapports X-1..X-8 (encours unique, résultat unique) | invariants verts |
| 3.3 | Import `fait_epargne` (inventaire dépôt) : DAV/DAT/obligatoire, groupe | encours épargne = balance |
| 3.4 | **Rapport 3 — FINA** : écriture `.xls`, F0/F1/F2/F5/F6/F10/F11 + cohérences inter-feuilles | FINA juillet reproduit |
| 3.5 | Rapports Direction/CA (mensuel + trimestriel) générés du socle | = TABLEAUX juillet/T2 |

**→ Jalon 3 : les rapports BCC et Direction se génèrent automatiquement.**

## PHASE 4 — Pilotage prévisionnel & rémunération
| Lot | Contenu | Validation |
|---|---|---|
| 4.1 | Saisie/versionnement `fait_budget` (multi-hypothèses) | budget 2026 saisi |
| 4.2 | Analyse d'écart (BU-*) par ligne × mois, mensuel & cumulé | = suivi budgétaire juin |
| 4.3 | Décomposition volume/prix (bridge, §22/§50) | écarts expliqués |
| 4.4 | Calcul des primes (correcteur PAR) — RH-PRIME | = calcul primes mai |

**→ Jalon 4 : la boucle planifier→suivre→analyser→récompenser est bouclée.**

## PHASE 5 — Transactions, conformité, extension
| Lot | Contenu |
|---|---|
| 5.1 | Import `fait_transaction_caisse` (brouillard USD+CDF) + mapping libellés (§54.1) |
| 5.2 | Statistiques opérations (dépôts/retraits/transferts) + AML/LBC-FT |
| 5.3 | Éléments de portée (BCC), pertes & fraudes (EAC), pilotage commercial par produit/canal |

## PHASE 6 — Production (application web multi-agences)
| Lot | Contenu |
|---|---|
| 6.1 | Passage Django : auth, rôles par agence, cloisonnement des données |
| 6.2 | Hébergement, sauvegardes testées, HTTPS, journal d'accès (§9) |
| 6.3 | Multi-utilisateurs, déploiement agences |

---

## CHEMIN CRITIQUE (dépendances)
```
Phase 0 (socle) ─► Phase 1 (crédit) ─► Phase 3.4 (FINA F5/F10/F11)
                                   └──► Phase 4.4 (primes, besoin PAR agent)
Phase 2 (magique) ─► Phase 3.1 (indicateurs) ─► Phase 3.4 (FINA F0/F1/F2)
                 └──► Phase 4.2 (écart, besoin réalisé comptable)
```
**Le crédit (Phase 1) et la comptabilité (Phase 2) sont les deux racines.** Tout le reste en dépend.
Commencer par elles maximise ce qu'on débloque tôt.

## POURQUOI CET ORDRE
1. **Crédit d'abord** : domaine le plus riche, déjà bien compris, alimente le plus de rapports, et la
   validation contre le Daily Tool est immédiate (données en main).
2. **Comptabilité ensuite** : le fichier magique existe et est fiable → portage cadré, débloque 3 rapports.
3. **Reporting après les deux racines** : un rapport n'est qu'une vue ; inutile de le coder avant que
   sa source soit validée.
4. **Budget/primes** : consomment des indicateurs déjà validés → risque faible.
5. **Web en dernier** : la valeur est dans les calculs justes ; l'enrobage multi-utilisateurs
   n'apporte rien tant que le moteur n'est pas sûr. Le construire trop tôt = « la toiture avant les murs ».

## POINTS DE DOCTRINE À TRANCHER (avant les lots concernés)
- ~~Résultat net~~ ✅ TRANCHÉ (§67) : Produits−Charges−Impôts, impôt 33 % à l'arrêté annuel
- ~~Solvabilité~~ ✅ TRANCHÉ (§68) : dénominateur = total actif de la période
- Périmètre exact dépôts à vue E.4 (bloque 3.1) — §28
- ~~Prorata~~ ✅ TRANCHÉ (§69) : jours OUVRÉS + calendrier ouvré à intégrer (date comptable ≠ calendaire)
- Tolérance d'arrondi encours X-1/X-3 (bloque 1.3/3.2)
