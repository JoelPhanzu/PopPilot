# PLAN D'IMPLÉMENTATION — Améliorations PopPilot
## Comment exécuter tout ça, pas à pas, sans rien écraser

---

## ÉTAPE 1 — Où déposer les fichiers (dézippés)

Dézippe ce dossier. Voici où va chaque élément dans ton projet PopPilot :

```
PopPilot/
├── api/
│   ├── engine/                      ← moteurs existants (NE PAS TOUCHER)
│   │   ├── moteur_filtres.py        ← COPIER ICI (nouveau)
│   │   ├── eljo_smart.py            ← COPIER ICI (nouveau)
│   │   ├── traitement_sage.py       ← COPIER ICI (nouveau)
│   │   ├── import_compte_resultat_agence.py  ← COPIER ICI (nouveau)
│   │   └── interets_par_agent.py    ← COPIER ICI (nouveau)
│   └── ...
├── supabase/
│   ├── 06_ajout_tables_ameliorations.sql   ← COPIER ICI (nouveau)
│   └── 07_ajout_tables_modules.sql         ← COPIER ICI (nouveau)
└── docs/
    ├── INSTRUCTIONS_AMELIORATIONS.md       ← COPIER ICI
    └── PLAN_IMPLEMENTATION.md              ← ce fichier
```

Règle simple : les **moteurs .py** vont dans `api/engine/`, les **.sql** dans `supabase/`,
les **.md** dans `docs/`. On AJOUTE des fichiers, on n'en remplace aucun.

---

## ÉTAPE 2 — Créer les nouvelles tables dans Supabase (SANS rien casser)

Dans Supabase → SQL Editor, exécute dans l'ordre (chacun est ADDITIF, rejouable) :
1. `06_ajout_tables_ameliorations.sql`  → compte de résultat agence, remboursements, SAGE, primes
2. `07_ajout_tables_modules.sql`        → Eljo Smart, archives, séries temporelles

⚠️ Ces scripts utilisent `CREATE TABLE IF NOT EXISTS` : ils NE recréent PAS tes tables
existantes et NE touchent PAS à tes données. Tu peux les exécuter en confiance.
Vérifie après : les nouvelles tables apparaissent, les anciennes et leurs données sont intactes.

---

## ÉTAPE 3 — Le message à donner à Claude Code

Copie-colle ceci dans Claude Code (dans VS Code) :

  « Lis docs/INSTRUCTIONS_AMELIORATIONS.md et docs/PLAN_IMPLEMENTATION.md.
   On ajoute des compléments à PopPilot, en mode STRICTEMENT ADDITIF : ne recrée aucune
   table (la base a des données), ne remplace aucun moteur ni endpoint existant, n'efface rien.
   Les nouveaux moteurs sont dans api/engine/ (moteur_filtres, eljo_smart, traitement_sage,
   import_compte_resultat_agence, interets_par_agent) — ils sont testés, intègre-les sans les
   réécrire. Les tables sont créées par supabase/06 et 07 (déjà exécutés, additifs).
   Construis dans cet ordre, en me montrant chaque étape avant de committer :
   1. Filtres sur le tableau de bord crédit (agence, sexe, produit, durée, client, agent, superviseur)
   2. Traitement SAGE : endpoint POST /sage/traiter (upload CBS + taux) → renvoie le .xlsx SAGE
   3. Compte de résultat par agence : import + page
   4. Intérêts par agent : import remboursements + jointure encours + page productivité
   5. Module Eljo Smart : messagerie qui appelle les moteurs (jamais d'invention, cloisonnement agence)
   6. Module Archives : bibliothèque de rapports remplaçables + éditables en ligne + séries temporelles
   7. Primes (après les intérêts par agent)
   Valide chaque calcul contre un chiffre connu. »

---

## ÉTAPE 4 — Ordre de construction détaillé et validation

| # | Chantier | Moteur fourni | Table(s) | Chiffre de validation |
|---|----------|---------------|----------|----------------------|
| 1 | Filtres tableau de bord | moteur_filtres.py | (aucune, lit fait_credit) | Ozone court terme cohérent |
| 2 | Traitement SAGE | traitement_sage.py | journal_sage_traite | équilibre débit=crédit (écart 0) |
| 3 | Compte de résultat agence | import_compte_resultat_agence.py | compte_resultat_agence | Victoire +38 316 ; total=MICROPOP |
| 4 | Intérêts par agent | interets_par_agent.py | fait_remboursement_encaisse | total intérêts août 344 116 |
| 5 | Eljo Smart | eljo_smart.py | eljo_conversation | « PAR mai Ozone » → vraie valeur |
| 6 | Archives | (à construire) | archive_rapport, serie_indicateur, archive_donnees | — |
| 7 | Primes | (à construire) | campagne_prime, fait_prime | correcteur PAR ×1/0,7/0,5/0 |

---

## DÉTAIL DES 3 NOUVELLES DEMANDES

### A. Filtres enrichis (chantiers 1-2)
`moteur_filtres.py` filtre les prêts AVANT calcul, sur : agence, agent, superviseur, sexe,
produits (multi), client, durée (court ≤12m ou groupe / moyen 12-24 / long >24).
Interface : une barre de filtres en haut du tableau de bord ; tout se recalcule au changement.
Les menus se peuplent via `valeurs_de_filtres()`. Le cloisonnement agence s'applique EN PLUS
(une agence ne filtre que dans son périmètre).

### B. Eljo Smart (messagerie)
Module de conversation. L'utilisateur pose une question ("PAR de mai à Ozone ?"), Eljo :
- analyse l'intention + date + agence (eljo_smart.analyser_question),
- appelle le VRAI moteur via l'API (jamais d'invention de chiffre),
- respecte le rôle : une AGENCE ne peut interroger que ses données,
- trace la conversation (table eljo_conversation).
Extensible : ajouter un indicateur = ajouter une entrée au registre INTENTIONS.
Interface : une page "Eljo Smart" avec un fil de discussion (question → réponse + valeur + source).

### C. Archives modifiables
Trois niveaux :
1. **Bibliothèque** (archive_rapport) : importer des rapports (Excel/PDF), les consulter, les
   télécharger. REMPLAÇABLES : déposer une version plus à jour incrémente `version` et garde
   l'ancienne (remplace_id) — historique préservé.
2. **Édition en ligne** (archive_donnees) : modifier les données d'un fichier directement dans
   l'interface — changer une valeur, ajouter des lignes/colonnes. Chaque modif est tracée
   (modifie_par, modifie_le).
3. **Séries temporelles** (serie_indicateur) : les indicateurs rangés par date → courbes
   d'évolution. Alimentées par l'import des historiques ET par les calculs mensuels de PopPilot.
   → un indicateur (ex. encours) affiché de 2023 à aujourd'hui, se prolongeant tout seul.

---

## RAPPEL — les 4 points SAGE à confirmer avant de figer
- Taux toujours unique pour le mois (rangé dans param_taux_change daté) ?
- N° Pièce / Code journal / N° Section toujours vides (SAGE génère) ?
- Type_Ecriture toujours "G" ?
- Comptes CDF : suffixe "1" attendu par SAGE ?
