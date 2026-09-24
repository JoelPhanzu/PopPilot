# Moteur de primes (chantier 4) — agents de crédit & superviseurs — VALIDÉ 31/31

## ⚠️ La prime NE dépend PAS des intérêts
Les intérêts mesurent la PROFITABILITÉ de l'agent (indicateur séparé).
La prime se calcule sur : volume décaissé, nombre, encours, épargne (couverture), PAR30, produit GL/IL.

## Cascade de calcul (fidèle au fichier CALCUL_PRIMES, feuille "AC et SUP")
1. **Éligibilité encours** : IL → encours≥100 000 ET nb≥25 ; GL → encours≥50 000 ET nb≥100.
2. **Type de prime** : Volume≥100% & Nombre≥80% → "Volume+Nombre" ; Volume≥100% → "Volume" ;
   Nombre≥80% → "Nombre" ; sinon "Aucune prime".
3. **Prime crédit** = (240 si V+N ; 150 si V ; 90 si N) × coefficient PAR.
   Correcteur PAR : ≤3%→×1 ; 3-5%→×0,7 ; 5-7%→×0,5 ; >7%→×0.
4. **Prime couverture** = 60 si (épargne/encours) ≥ 29,5%, sinon 0. (indépendante du PAR)
5. **Prime totale** = crédit + couverture, + motif explicatif automatique.

## Validation
31/31 agents du fichier de mai reproduits AU CENTIME. Ex. BAZOMBWA BELI FRANK (IL) :
type "Volume", coeff PAR 0,7 → crédit 105 + couverture 60 = 165. ✓

## Source unique
Le PAR30 par agent vient du moteur crédit (engine/par.py), JAMAIS ressaisi.
Le barème est dans param_bareme_prime (daté). Le résultat s'historise dans fait_prime + campagne_prime.

## TOUTES les catégories sont implémentées et VALIDÉES au centime :
1. **AC et SUP** (agents crédit + superviseurs) : cascade éligibilité → type → PAR → couverture. 31/31.
2. **Superviseur épargne** : palier selon montant d'épargne réalisé (≥50k→60, ≥70k→100, ≥100k→200).
3. **Agents recouvrement** : 1% (91-180j) + 3% (181+) + 5% (radié) sur montants recouvrés. Ex JUNIOR 339,84 ✓.
4. **Responsable recouvrement** : 0,3% / 0,5% / 1%. Ex KADIMA 94,90 ✓.
5. **Fonctions support** (superviseurs siège) : (prime volume + prime PAR + prime couverture) × nb agences.
   Ex VICTOIRE unitaire 15 × 7 = 105 ✓.
6. **Direction agence** : % du résultat comptable (Directeur 1%, Adjoint 0,5%). Ex VICTOIRE 739,17 ✓.
   Pas de prime si résultat négatif.
7. **Direction siège** : % de la profitabilité globale (DG 1%, Dir. ops 0,6%, DAF 0,3%). Ex DG 953,42 ✓.
Fonctions dans moteur_primes.py : calculer_prime_agent, prime_superviseur_epargne,
prime_recouvrement, prime_fonction_support, prime_direction_agence, prime_direction.
Les bases (résultat par agence, PAR, recouvrement) viennent des moteurs / sources déjà en place.
