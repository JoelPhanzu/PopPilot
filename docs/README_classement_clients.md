# Moteur classement clients (Top N) — enrichissement tableaux de bord

## Ce qu'il fait
Classe les clients (AGRÉGÉ par client, tous crédits cumulés) selon un critère, en Top N.
Meilleurs ou pires, N paramétrable (10, 20, 50...).

## 5 critères (validés CDG)
- **encours** (stock) : total encours crédit du client → repérer les gros clients / concentration.
- **par** (stock) : total encours en retard + max jours de retard → LISTE DE RELANCE prioritaire.
- **decaissement** (flux, période [début→fin]) : total déboursé sur la période → clients actifs.
- **epargne** (stock) : solde d'épargne → gros épargnants à fidéliser.
- **fidelite** (stock) : nombre de crédits + ancienneté → bons clients récurrents.

## Doctrine respectée
- FLUX (décaissement) = période ; STOCK (encours, PAR, épargne, fidélité) = date de valorisation.
- Cloisonnement agence appliqué EN AMONT (l'API ne passe que les prêts visibles par l'utilisateur).
- Se combine avec les filtres (agence, agent, superviseur, produit, durée...).

## Validé sur mai 2026
- Top encours : BUNGANA PAPE NELLY 81 860 (2 crédits).
- Pires PAR : MUKADI KABEYA DEPS 21 872 en retard (144j) ; NTUMBA MBIYA 328j (proche radiation).

## Sécurité / confidentialité
Les classements affichent des données clients nominatives → réservés aux rôles habilités,
cloisonnés par agence. Une agence ne voit que ses clients.
