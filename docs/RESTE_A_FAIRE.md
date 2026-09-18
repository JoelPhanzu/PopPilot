# RESTE À FAIRE — plateforme MICROPOP (registre des chantiers ouverts)

> Tenu à jour au fil des sessions. Ce qui est ✅ est construit ET validé sur données réelles.

## MOTEURS CONSTRUITS ET VALIDÉS ✅
- **Socle de données** : 29 tables, historisation (idempotence, snapshot daté, calendrier ouvré RDC).
- **Crédit** (Phase 1) : import extraction, PAR1/30/90, provisions (barème), croissance, coût du risque,
  migrations, décaissement (filtre dates), roster/objectifs, orphelins, statut d'agence, provision
  manuelle Goma. Validé écart nul vs Dashboard.
- **Comptabilité** (Phase 2) : import balance (USD et CDF), fichier magique en Python, bilan + compte
  de résultat, mapping compte→agrégat, conversion. Validé vs fichier magique.
- **Indicateurs prudentiels** (Phase 3) : 17 ratios, fonds propres 2 versions, moyennes de période,
  E4 liquidité, B2. PAR depuis source unique.
- **Épargne** : import inventaire (170k comptes), ventilation type/devise/groupe, nb épargnants.
- **FINA** : F0,F1,F2,F3,F5,F6,F7,F10,F11 remplis depuis balance CDF ; cohérences inter-feuilles ;
  ventilation groupe LISANGA ; écriture du .xls.
- **AML/LBC-FT** : opérations espèces par seuil, transferts GL (USD→CDF), portefeuille client
  (PP/PM/groupe, solde_fin), localisation par province.
- **Budget — SUIVI** : réalisé depuis balance, mapping dynamique, 3 niveaux (mensuel, cumulé/annuel,
  cumulé/à-date). Doctrine figée.
- **Analyses ad hoc DGA** : provisions mois vs mois, migrations, prévision de migration + dotation
  projetée. Moteur de projection à +N jours.
- **Système de paiement** : comptes actifs/dormants (6 mois), types de transactions. ⚠️ À CORRIGER.

## CHANTIERS OUVERTS / EN PLAN

### 1. Budget — ÉLABORATION (gros chantier, plus tard)
Construire le budget prévisionnel complet, feuille par feuille :
- Encours crédit projeté (moteur de tout le reste : les produits d'intérêts en découlent)
- Épargne projetée
- Charges et produits PAR AGENCE → consolidés (le consolidé VIENT des agences, pas l'inverse)
- RH (effectifs projetés), immobilisations
- Bilan et compte de résultat prévisionnels, indicateurs projetés
- Multi-hypothèses (H1, H2, H3) : croissance, ouverture d'agences, contexte éco
- Base « scientifique » : résultats passés + tendances + investissements projetés + hypothèses
→ Méthode de prévision à recueillir auprès du CDG (par quel bout on commence, comment on prévoit).

### 2. Système de paiement — CORRECTIONS
- Rapport à revoir en profondeur (CDG : "beaucoup à corriger"). Détails à recueillir.
- Point déjà noté : ordre colonnes Volume/Valeur (croisé vs en-tête), à confirmer.
- Feuille "Banques et IMF" (comptes actifs) 138 colonnes : structure à cadrer avant remplissage.

### 3. AML — sections restantes (complétées manuellement par Conformité)
- Ventilations par secteur d'activité client, alertes, canaux, déclarations : hors plateforme (Conformité).

### 4. FINA — F10 ventilation sectorielle
- Taux sectoriels saisis manuellement (fait). Si un jour secteur dans l'extraction crédit → auto.

### 5. Points de doctrine / données à recueillir
- Grille complète des réintégrations fiscales (DAF) — pour l'impôt annuel (§67).
- Nombre d'agents "officiel" RH pour B2 (vs roster objectifs).
- Fériés RDC : reports d'arrêté ministériel à saisir au fil de l'eau.
- Primes : moteur PAS ENCORE construit (barème en base, correcteur PAR défini). À faire.

### 6. Assemblage plateforme (EN COURS — c'est ce qu'on attaque)
- Interface unifiée qui relie tous les moteurs : import → calcul → rapports.
- ✅ **Import depuis le web** : `POST /import/{domaine}` (api/import_cbs.py) + page `/import`
  du front Next.js. Crédit, balance, épargne, objectifs, budget. Réservé DIRECTION/CDG,
  idempotent, journal des imports (`GET /imports`). Tests : `tests/test_import_api.py`.
- Reste côté front : pages compta/indicateurs, épargne, budget, rapports réglementaires,
  export Excel.
- Orchestration : un mois = importer les sources → générer tous les rapports.

## PRINCIPES DIRECTEURS (rappel)
- La plateforme s'en tient aux données sources (balance, extractions), SANS retraitement.
- Source unique : chaque donnée (PAR, encours…) calculée une fois, réutilisée partout.
- Historisation : tout est daté, consultable par date, mois par mois.
- Multi-devises : USD et CDF natifs ; conversion seulement quand le rapport cible l'exige (FINA=CDF,
  AML transferts=CDF ; système paiement=PAS de conversion).
