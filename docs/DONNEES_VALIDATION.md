# Jeu de validation — d'où viennent les chiffres de l'écart nul

La plateforme ne vaut que si ses moteurs retrouvent, au centime, les chiffres des fichiers
réels. Ce document dit **quel fichier local alimente quel test**, et comment relancer la
campagne. Les fichiers sources sont de vraies données clients : ils ne sont **jamais** au dépôt.

## Où poser les fichiers
`PopPilot/data_local/` (ignoré par git), ou n'importe quel dossier désigné par la variable
d'environnement `POPPILOT_DONNEES` :

```
set POPPILOT_DONNEES=D:/chemin/vers/les/extractions
```

## Lancer la campagne
```
cd api
.venv\Scripts\activate
python tests/lancer_tous.py
```

Le verdict distingue **trois** états, jamais confondus :

| Verdict | Sens |
|---|---|
| `VALIDE` | les chiffres recalculés collent aux fichiers réels |
| `PARTIEL` / `NON VALIDE` | des sources manquent : **rien n'a été vérifié**, ce n'est pas un succès |
| `EN ECHEC` | un écart est apparu — ne livrer aucun chiffre avant de l'avoir expliqué |

> Auparavant, un fichier absent provoquait un `return` silencieux et la suite affichait
> quand même « Phase 1 validée ». Un faux vert est pire que pas de test : c'est corrigé.

## Correspondance fichier local → test

| Fichier dans `data_local/` | Origine (dossier CONTRÔLE DE GESTION) | Sert à |
|---|---|---|
| `Enours_MAI_2026_.xls` | `RAPPORTS/Rapport Mensuel/2026/MAI 2026/Enours MAI 2026_.xls` | Phase 1, Phase 3 |
| `Encours_crédit_AVRIL_2026.xlsx` | `RAPPORTS/Rapport Mensuel/2026/AVRIL/Encours crédit AVRIL 2026.xlsx` | Phase 1 (croissance, migrations) |
| `Encours_credit_JUILLET_2026.xlsx` | `RAPPORTS/Rapport Mensuel/2026/Juillet 2026/Encours Crédit Juillet 2026.xlsx` | Phase 3, FINA |
| `Encours_credit_DECEMBRE_2025.xls` | `RAPPORTS/Rapport Mensuel/2025/Décembre 2025/Ressources/Encours crédit au 31  Décembre.xls` | Phase 3 (moyennes de période) |
| `BALANCE.xlsx` | `OUTILS DE PILOTAGE/BALANCE.xlsx` | Phase 2 (balance SAGE brute) |
| `ETATS_FINANCIERS_USD_JUILLET_2026.xlsx` | `…/Juillet 2026/ETATS FINANCIERS USD JUILLET 2026.xlsx` | Phase 2 (réf.), Phase 3 (balance USD) |
| `ETATS_FINANCIERS_USD_MAI_2026.xlsx` | `…/MAI 2026/ETATS FINANCIERS USD MAI 2026.xlsx` | Phase 3 |
| `ETATS_FINANCIERS_USD_DEC_2025.xlsx` | `…/Décembre 2025/ETATS FINANCIERS USD DEC 2025.xlsx` | Phase 3 |
| `ETATS_FINANCIERS_CDF_JUILLET_2026.xlsx` | `…/Juillet 2026/ETATS FINANCIERS CDF JUILLET 2026.xlsx` | FINA (rapport en CDF) |
| `Inventaire_depot_juillet_2026_Inventaire_depot_script___3_.xlsx` | `…/Juillet 2026/Inventaire_depot_juillet_2026(Inventaire_depot_script) (4).csv.xlsx` | Épargne, Phase 3 (E4), FINA |
| `OBJECTIF.xlsx` | `OUTILS DE PILOTAGE/OBJECTIF.xlsx` | Phase 1 (orphelins), Phase 3 (B2) |

**Ce rapprochement n'est pas supposé, il est prouvé** : chaque fichier est confirmé par le
fait que les moteurs retrouvent les montants de référence (PAR30 mai 1 052 118 ; provisions
938 244,42 ; total actif 12 592 520,01 ; épargne 169 799 comptes ; LISANGA 3 172 238 623 CDF).

## Décisions prises (CDG)
- **Balance des indicateurs prudentiels : USD.** Les fonds propres et les 17 ratios sont
  libellés en USD, cohérents avec la Phase 2. Le **CDF est réservé au FINA**, rapport en francs.
- **Plus de fichiers « combinés »** `<Mois>_Encours_et_balance.xlsx`. Ils n'étaient qu'un
  assemblage manuel d'un environnement antérieur. Les tests lisent désormais les fichiers
  **tels que le CBS et la compta les produisent** : extraction crédit d'un côté, états
  financiers de l'autre.
- **Inventaire épargne : `.csv` ou `.xlsx` acceptés.** Le CBS exporte tantôt l'un tantôt
  l'autre ; `ingest/import_epargne.py` détecte le format et le séparateur, et lit par
  **nom de colonne** (l'inventaire d'août intercale une colonne « Mois année » qui décale tout).

## Portée actuelle
23 cas sur 8 suites, tous verts :
Phase 0 socle · sécurité API · Phase 1 crédit · Phase 2 compta · Phase 3 indicateurs ·
épargne · FINA calcul · FINA écriture .xls.
