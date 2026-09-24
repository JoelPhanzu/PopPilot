# Moteur traitement SAGE (chantier 5) — testé, écart nul

## Ce qu'il fait
Transforme le Grand Livre brut du CBS (feuille "Grand_livre", 9 colonnes) en fichier
au format SAGE (12 colonnes, ordre exact), prêt à importer dans la comptabilité SAGE.
L'utilisateur ne fournit QUE l'extraction CBS ; PopPilot rend le fichier SAGE.

## Règles appliquées (validées)
1. **CG (compte reformaté)** : points retirés, suffixe devise (USD→0, CDF→1), complété à 8 chiffres.
   Ex. `3.2.5.0.3` (USD) → `32503000` ; `3.2.7.0.1.1` (USD) → `32701100`.
2. **Conversion CDF** : Montant devise = tel quel ; Parité = taux du mois (USD) ou 1 (CDF) ;
   Montant CDF = montant × taux (USD) ou tel quel (CDF) ; sens `d`→Débit, `c`→Crédit.
3. **Vides** (SAGE les gère) : N° Pièce, Code journal, N° Section.
4. **Type_Ecriture** = "G".

## Contrôle intégré
Total Débit CDF = Total Crédit CDF (équilibre comptable). Sur septembre : 29 269 732 003,35 des
deux côtés, écart 0,00. Un écart non nul = alerte (fichier non importable en l'état).

## Validation
Ligne testée contre le fichier de référence : 5114,47 USD × 2365 = 12 095 721,55 CDF ✓ (exact).

## À CONFIRMER avec le CDG (points où je n'ai pas voulu supposer)
- Le taux est-il TOUJOURS unique pour le mois (comme FINA/AML) ? → oui supposé, à ranger dans
  param_taux_change daté.
- N° Pièce / Code journal / N° Section : toujours vides ? (SAGE génère) — supposé oui.
- Type_Ecriture : toujours "G" ? — supposé oui.
- Les comptes CDF : le suffixe devient "1" — confirmer que SAGE attend bien ça (ex. 33114100).

## Intégration PopPilot
- Endpoint : POST /sage/traiter (upload fichier CBS + taux du mois) → renvoie le .xlsx SAGE.
- Table `journal_sage_traite` (déjà dans 06_ajout_tables.sql) : trace chaque traitement.
- Page : "Import → SAGE" (réservée DIRECTION/CDG).
