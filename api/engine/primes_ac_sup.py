"""
Primes des AGENTS DE CRÉDIT et SUPERVISEURS (« AC et SUP ») — orchestration.

La RÈGLE est celle de engine/moteur_primes.calculer_prime_agent (validée 31/31 au centime contre
CALCUL_PRIMES de mai) : ce module ne la réécrit pas, il lui fournit ses bases depuis le socle.

BASES (une ligne par agent ou superviseur ACTIF du roster du mois ; source unique) :
  - volume / nombre décaissés du MOIS de l'arrêté ...... tableau de bord crédit (flux 1er → arrêté)
  - objectifs volume / nombre .......................... fichier OBJECTIF du mois (param_objectif)
  - encours (volume) et nombre de crédits (dossiers) ... tableau de bord crédit (stock à l'arrêté)
  - PAR30 .............................................. tableau de bord crédit (jamais ressaisi)
  - épargne ............................................ inventaire dépôt DU MÊME ARRÊTÉ : solde (USD)
                                                          des clients du portefeuille (décision CDG :
                                                          « l'épargne des clients de son portefeuille »).
                                                          Un client suivi par deux agents est rattaché
                                                          à celui qui porte son plus gros encours.
  - produit GL / IL .................................... majorité des dossiers du portefeuille
                                                          (LISANGA = GL), comme la feuille « AC et SUP ».
Superviseurs : même cascade, sur leur portefeuille et la somme des objectifs de leurs agents.

⚠️ La prime ne dépend PAS des intérêts (indicateur de profitabilité distinct).
Pré-requis bloquants (jamais de prime sur une base incomplète) : roster + objectifs du mois,
inventaire épargne de l'arrêté.
"""
from __future__ import annotations

import datetime as dt
from collections import defaultdict

from sqlalchemy import case, func, select

from engine.moteur_primes import BAREME, calculer_prime_agent
from engine.tableau_de_bord_credit import tableau_de_bord_credit
from socle.schema import FaitCredit, FaitEpargne, get_session


def _epargne_par_client(s, date_arrete: dt.date) -> dict[str, float]:
    from engine.etats_financiers import taux_change
    taux = taux_change(s, date_arrete)
    E = FaitEpargne
    solde = func.sum(case((E.devise == "CDF", E.solde_actuel / taux), else_=E.solde_actuel))
    return {c: v or 0.0 for c, v in s.execute(
        select(E.id_client, solde).where(E.date_arrete == date_arrete).group_by(E.id_client)).all()}


def primes_ac_sup(date_arrete: dt.date, db_path="socle/micropop.db", bareme=BAREME) -> dict:
    s = get_session(db_path)
    try:
        if not s.execute(select(func.count()).select_from(FaitEpargne)
                         .where(FaitEpargne.date_arrete == date_arrete)).scalar():
            raise ValueError(f"Inventaire épargne du {date_arrete} non importé : la couverture "
                             "(épargne des clients du portefeuille) est indispensable à la prime.")
        epargne = _epargne_par_client(s, date_arrete)
        prets = s.execute(select(FaitCredit.numero_client, FaitCredit.agence, FaitCredit.agent_credit,
                                 FaitCredit.superviseur, FaitCredit.encours, FaitCredit.est_groupe)
                          .where(FaitCredit.date_arrete == date_arrete)).all()
    finally:
        s.close()

    debut = date_arrete.replace(day=1)
    niveaux = {n: tableau_de_bord_credit(date_arrete, debut, date_arrete, niveau=n, db_path=db_path)
               for n in ("agent", "superviseur")}
    if not niveaux["agent"]["roster_du_mois"]:
        raise ValueError(f"Aucun roster / objectif importé pour {date_arrete:%m/%Y} : "
                         "importer le fichier OBJECTIF du mois avant de calculer les primes.")

    # Client → agent qui porte son plus gros encours (épargne comptée une seule fois).
    porteur: dict[str, tuple] = {}
    poids: dict[tuple, float] = defaultdict(float)
    for p in prets:
        poids[(p.numero_client, p.agence, p.agent_credit, p.superviseur)] += p.encours or 0.0
    for (client, agence, agent, sup), enc in poids.items():
        if client not in porteur or enc > porteur[client][0]:
            porteur[client] = (enc, agence, agent, sup)
    ep_agent, ep_sup = defaultdict(float), defaultdict(float)
    for client, (_, agence, agent, sup) in porteur.items():
        ep_agent[(agence, agent)] += epargne.get(client, 0.0)
        ep_sup[(agence, sup)] += epargne.get(client, 0.0)
    gl = defaultdict(lambda: [0, 0])
    for p in prets:
        for cle in (("agent", p.agence, p.agent_credit), ("superviseur", p.agence, p.superviseur)):
            gl[cle][0 if p.est_groupe else 1] += 1

    resultats = {}
    for niveau, epargne_de in (("agent", ep_agent), ("superviseur", ep_sup)):
        lignes = []
        for l in niveaux[niveau]["lignes"][1:]:
            if l["statut"] != "actif":
                continue
            nb_gl, nb_il = gl[(niveau, l["agence"], l["designation"])]
            produit = "GL" if nb_gl > nb_il else "IL"
            ep = epargne_de.get((l["agence"], l["designation"]), 0.0)
            r = calculer_prime_agent(
                produit=produit, volume_realise=l["decaisse_volume"],
                volume_objectif=l["objectif_volume"] or 0.0, nombre_realise=l["decaisse_nombre"],
                nombre_objectif=l["objectif_nombre"] or 0.0, encours_volume=l["encours"],
                encours_nombre=l["nb_credits"], solde_epargne=ep, par30=l["pct_par30"],
                bareme=bareme)
            lignes.append({"agence": l["agence"], "nom": l["designation"], "fonction": niveau,
                           "volume_realise": l["decaisse_volume"], "volume_objectif": l["objectif_volume"],
                           "nombre_realise": l["decaisse_nombre"], "nombre_objectif": l["objectif_nombre"],
                           "encours": l["encours"], "nb_credits": l["nb_credits"], "epargne": ep,
                           "par30": l["pct_par30"], "sans_objectif": not l["objectif_nombre"], **r})
        resultats[niveau] = lignes

    alertes = [f"{x['nom']} ({x['agence']}) : aucun objectif dans le fichier OBJECTIF du mois."
               for x in resultats["agent"] if x["sans_objectif"]]
    return {"arrete": date_arrete.isoformat(), "periode": [debut.isoformat(), date_arrete.isoformat()],
            "agents": resultats["agent"], "superviseurs": resultats["superviseur"],
            "total_agents": round(sum(x["prime_totale"] for x in resultats["agent"]), 2),
            "total_superviseurs": round(sum(x["prime_totale"] for x in resultats["superviseur"]), 2),
            "bareme": {k: v for k, v in bareme.items() if k != "par_tranches"},
            "alertes": alertes,
            "orphelins_exclus": [{"agence": l["agence"], "encours": l["encours"]}
                                 for l in niveaux["agent"]["lignes"][1:] if l["statut"] == "orphelin"]}
