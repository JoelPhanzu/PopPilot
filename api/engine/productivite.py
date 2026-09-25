"""
Profil de PRODUCTIVITÉ par agent, superviseur, agence (chantiers 1-2).

Assemble des sources existantes, sans nouvelle définition d'indicateur :
  - encours, nb crédits, nb clients (pondéré), PAR30 : engine.par._agrege, sur les prêts
    de l'arrêté (même calcul que /par) ;
  - décaissements du mois : même définition que engine.decaissement.decaissements
    (date_deboursement dans [1er du mois ; arrêté]) ;
  - intérêts, capital, pénalités ENCAISSÉS : fait_remboursement_encaisse (hiérarchie
    résolue à l'import). Mesure la PROFITABILITÉ, n'entre pas dans les primes.

RÈGLE ROSTER / ORPHELIN (docs/REGLE_ROSTER_ORPHELIN.md) — agents et superviseurs :
  - le roster DU MOIS (dim_employe, date_debut dans le mois) fait autorité ;
  - absent du roster → « PORTEFEUILLE ORPHELIN » de son agence (jamais dans la performance
    d'un autre) ; agence FERMÉE → « PORTEFEUILLE GELÉ » (ni orphelin ni performance) ;
  - pas de roster pour le mois → AUCUN profil individuel (on ne sait pas qui est actif).
Le niveau agence ne dépend pas du roster.

INVARIANT (testé) : la somme des lignes, orphelins/gelés/non rattachés compris, redonne les
totaux de l'institution (encours de /par, intérêts importés, décaissements du moteur).
"""
from __future__ import annotations

import datetime as dt
from collections import defaultdict

from sqlalchemy import func, select

from socle.schema import DimEmploye, FaitCredit, FaitRemboursementEncaisse, get_session
from engine.par import _agrege

NIVEAUX = ("agent", "superviseur", "agence")
ORPHELIN, GELE, NON_RATTACHE = "PORTEFEUILLE ORPHELIN", "PORTEFEUILLE GELÉ", "(non rattaché)"


def _roster_du_mois(s, date_arrete: dt.date) -> dict[str, set] | None:
    lignes = s.execute(select(DimEmploye.nom, DimEmploye.fonction, DimEmploye.agence)
                       .where(DimEmploye.date_debut >= date_arrete.replace(day=1),
                              DimEmploye.date_debut <= date_arrete)).all()
    if not lignes:
        return None
    r = {"agent_credit": set(), "superviseur": set()}
    for nom, fonction, agence in lignes:
        if fonction in r:
            r[fonction].add((nom.strip().upper(), (agence or "").strip().upper()))
    return r


def profil_productivite(date_arrete: dt.date, niveau: str = "agence",
                        db_path="socle/micropop.db") -> dict:
    if niveau not in NIVEAUX:
        raise ValueError(f"niveau inconnu : {niveau} (attendu {', '.join(NIVEAUX)})")
    from socle.agences import agences_non_productives as agences_fermees

    s = get_session(db_path)
    try:
        prets = s.execute(select(
            FaitCredit.agence, FaitCredit.agent_credit, FaitCredit.superviseur,
            FaitCredit.numero_client, FaitCredit.encours, FaitCredit.jours_de_retard,
            FaitCredit.date_deboursement, FaitCredit.montant_debourse,
        ).where(FaitCredit.date_arrete == date_arrete)).all()
        remb = s.execute(select(
            FaitRemboursementEncaisse.agence, FaitRemboursementEncaisse.agent_credit,
            FaitRemboursementEncaisse.superviseur,
            func.sum(FaitRemboursementEncaisse.interets_rembourses),
            func.sum(FaitRemboursementEncaisse.capital_rembourse),
            func.sum(FaitRemboursementEncaisse.penalites_rembourses), func.count(),
        ).where(FaitRemboursementEncaisse.date_arrete == date_arrete).group_by(
            FaitRemboursementEncaisse.agence, FaitRemboursementEncaisse.agent_credit,
            FaitRemboursementEncaisse.superviseur)).all()
        roster = _roster_du_mois(s, date_arrete)
        fermees = agences_fermees(s)
    finally:
        s.close()
    if not prets:
        raise ValueError(f"Aucun prêt pour l'arrêté {date_arrete}. Importer d'abord l'extraction.")

    if niveau != "agence" and roster is None:
        return {"arrete": date_arrete.isoformat(), "niveau": niveau, "roster_du_mois": False,
                "lignes": [], "message": (
                    f"Aucun roster importé pour {date_arrete:%m/%Y} : impossible de distinguer "
                    "les agents actifs des orphelins. Importer le fichier OBJECTIF du mois.")}

    # Noms du roster rapprochés des noms CBS (superviseurs en nom court) : socle/roster.py.
    from socle.roster import correspondances, normaliser
    if roster is not None:
        for fonction, attr in (("agent_credit", 1), ("superviseur", 2)):
            base = {(normaliser(n), normaliser(a)) for n, a in roster[fonction]}
            noms = [(r[attr], r[0]) for r in remb] + [
                (p.agent_credit if attr == 1 else p.superviseur, p.agence) for p in prets]
            roster[fonction] = base | set(correspondances(base, noms))

    def cle(agence, agent, superviseur) -> tuple[str, str]:
        """(agence, désignation) de la ligne où tombe ce prêt / ce remboursement."""
        ag = agence or NON_RATTACHE
        if agence is None:
            return (NON_RATTACHE, NON_RATTACHE)
        if niveau == "agence":
            return (ag, ag)
        if ag.strip().upper() in fermees:
            return (ag, GELE)
        nom = agent if niveau == "agent" else superviseur
        fonction = "agent_credit" if niveau == "agent" else "superviseur"
        if nom and (normaliser(nom), normaliser(ag)) in roster[fonction]:
            return (ag, nom)
        return (ag, ORPHELIN)

    debut = date_arrete.replace(day=1)
    groupes: dict[tuple, list] = defaultdict(list)
    decaisse: dict[tuple, list] = defaultdict(lambda: [0, 0.0])
    for p in prets:
        k = cle(p.agence, p.agent_credit, p.superviseur)
        groupes[k].append(p)
        if p.date_deboursement and debut <= p.date_deboursement <= date_arrete:
            decaisse[k][0] += 1
            decaisse[k][1] += p.montant_debourse or 0.0
    encaisse: dict[tuple, list] = defaultdict(lambda: [0.0, 0.0, 0.0, 0])
    for agence, agent, superviseur, it, cap, pen, n in remb:
        e = encaisse[cle(agence, agent, superviseur)]
        e[0] += it or 0.0
        e[1] += cap or 0.0
        e[2] += pen or 0.0
        e[3] += n

    effectifs: dict[str, int] = defaultdict(int)
    if roster:
        for _nom, agence in roster["agent_credit"]:
            effectifs[agence] += 1

    lignes = []
    for k in sorted(set(groupes) | set(encaisse)):
        agence, designation = k
        a = _agrege(groupes.get(k, []), designation, niveau.upper())
        e = encaisse.get(k, [0.0, 0.0, 0.0, 0])
        d = decaisse.get(k, [0, 0.0])
        ligne = {
            "agence": agence, "designation": designation,
            "statut": ("orphelin" if designation == ORPHELIN else "gele" if designation == GELE
                       else "non_rattache" if designation == NON_RATTACHE else "actif"),
            "encours": a.encours, "nb_credits": a.nb_credits, "nb_clients": a.nb_clients,
            "par30": a.par30, "pct_par30": a.pct_par30,
            "decaisse_nombre": d[0], "decaisse_volume": d[1],
            "interets_encaisses": e[0], "capital_encaisse": e[1], "penalites_encaissees": e[2],
            "nb_remboursements": e[3],
        }
        if niveau == "agence" and roster:
            n = effectifs.get(agence.strip().upper(), 0)
            ligne["effectif_agents"] = n
            ligne["decaisse_par_agent"] = (d[1] / n) if n else None
        lignes.append(ligne)

    return {"arrete": date_arrete.isoformat(), "niveau": niveau,
            "roster_du_mois": roster is not None, "lignes": lignes,
            "totaux": {c: sum(l[c] for l in lignes) for c in (
                "encours", "nb_credits", "decaisse_nombre", "decaisse_volume",
                "interets_encaisses", "capital_encaisse", "penalites_encaissees",
                "nb_remboursements")}}
