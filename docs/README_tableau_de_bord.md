# Moteur tableau de bord (chantiers 1-2) — la BASE du métier

## Doctrine FLUX vs STOCK (validée CDG)
Deux contrôles de temps INDÉPENDANTS dans l'écran :
- **Période de flux** [début → fin] : indicateurs cumulatifs (décaissement, remboursements,
  intérêts/commissions/pénalités encaissés, migrations, coût du risque, production, radiations).
- **Date de valorisation** (une date) : indicateurs de stock (encours, PAR1/30/90, provisions solde,
  nb clients, nb crédits, épargne solde).

Exemple : on peut afficher les décaissements du [01→31/05] ET l'encours au 30/05, sans confusion.

## Catégories de produit (règle CDG)
- GL (groupe) = "Crédit LISANGA" ; IL (individuel) = tout le reste.
- PME = tout crédit dont le décaissement >= 15 000.

## Validé sur mai 2026
- STOCK au 30/05 : encours 10 814 331, PAR30 9,73 %.
- FLUX décaissement : tout mai 517 / 1re quinz. 134 / 2e quinz. 383 (134+383=517, cumulatif ✓).
- Ventilation GL/IL/PME intégrée.

## Se combine avec moteur_filtres.py
agence, agent, superviseur, sexe, produit (multi), durée (court/moyen/long), client.
Le filtre de temps (flux/stock) + les filtres d'axe s'appliquent ensemble.

## À retenir pour l'interface
Chaque tableau de bord a EN HAUT : un sélecteur de période (flux) + un sélecteur de date (stock)
+ les filtres d'axe. Les indicateurs de flux réagissent à la période ; les stocks à la date.
