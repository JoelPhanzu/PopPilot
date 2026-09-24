# RÈGLE FONDAMENTALE — Roster mensuel & portefeuille orphelin

> S'applique à TOUS les calculs de performance et de prime. Ne jamais contourner.

## Principe
Toute performance (décaissement, PAR, recouvrement, primes, productivité) n'est calculée
QUE pour les agents figurant sur la LISTE DU MOIS fournie à PopPilot (le roster + objectifs).
Concerne : agents de crédit, superviseurs, agents de recouvrement.

La liste mensuelle fait AUTORITÉ. Un agent = performance seulement s'il y est inscrit.

## Portefeuille orphelin
Tout agent ABSENT de la liste du mois (parti, licencié, muté) dont le portefeuille
n'a PAS été réaffecté à un agent actif → ses chiffres basculent AUTOMATIQUEMENT dans
le PORTEFEUILLE ORPHELIN, clairement identifié (jamais dilués dans la performance d'autrui,
jamais versés en prime).

But : ne pas primer un absent, ne pas fausser la productivité d'une agence, et RENDRE VISIBLE
l'encours orphelin pour qu'il soit réaffecté et recouvré.

## Chaîne de rattachement (déjà construite)
numéro de dossier → agent inscrit dans l'encours crédit → présent sur la liste du mois ?
  - OUI → performance rattachée à cet agent
  - NON → portefeuille orphelin

## Points à confirmer avec le CDG (avant implémentation définitive)
- [ ] Agents de recouvrement : le montant recouvré va-t-il à l'agent de recouvrement ACTIF
      qui l'a encaissé (même si le dossier d'origine appartenait à un agent parti) ?
      Hypothèse : OUI (c'est lui qui a fait le travail). L'orphelin concerne le portefeuille
      non réaffecté, pas l'action de recouvrement.
- [ ] Confirmer que la liste du mois inclut les objectifs de recouvrement pour les agents recouv.

## Implémentation
- Le roster mensuel est importé (dim_employe + param_objectif, datés).
- Chaque moteur de performance (par, décaissement, intérêts par agent, primes, recouvrement)
  filtre sur le roster du mois AVANT calcul. Absent du roster → orphelin.
- Les agences FERMÉES (ex. Goma) : portefeuille gelé, traité à part (déjà en place).
