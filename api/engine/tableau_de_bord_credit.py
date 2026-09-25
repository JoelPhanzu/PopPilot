"""
Tableau de bord CRÉDIT complet (chantiers 1-2) — colonnes du DailyTool, doctrine FLUX / STOCK.

Aucune règle nouvelle : ce module ASSEMBLE les moteurs validés sur un seul chargement.
  - sélection des prêts ........ engine.moteur_filtres.filtrer_prets (agence, sexe, produits,
                                   durée, client, agent, superviseur) — AVANT tout calcul
  - STOCK à la date de valorisation (arrêté) :
      encours, PAR1/30/90, clients . engine.par._agrege
      provisions .................. engine.derivation (barème prêt par prêt) + complément DAF
                                    par agence (seulement si la sélection garde des agences entières)
  - STOCK M-1 (arrêté précédent) : encours, clients, crédits → croissance
  - FLUX sur [début ; fin] :
      décaissements (nb, volume, GL/IL/PME) . engine.moteur_tableau_de_bord.decaissement_periode
      P15 = décaissements du 1er au 15 du mois de la date de fin (objectif = ½ objectif mensuel)
      coût du risque, entrées en PAR, migrations . engine.migrations.migrations_sur (M-1 → arrêté)
  - objectifs et effectif ....... roster + objectifs DU MOIS (dim_employe, param_objectif)
  - FLUX encaissés sur [début ; fin] : intérêts, capital, pénalités (fait_remboursement_encaisse,
    hiérarchie résolue à l'import) ; « recouvré sur PAR » = encaissé sur les dossiers en retard
    à l'arrêté M-1. Un remboursement suit la sélection par son n° de dossier.

NIVEAUX : « agence », « superviseur », « agent », « client ». Règle roster (non négociable) :
aux niveaux superviseur/agent, un nom absent du roster du mois → PORTEFEUILLE ORPHELIN de son
agence ; agence fermée ou suspendue → PORTEFEUILLE GELÉ ; sans roster du mois → pas de ligne
individuelle. Les noms courts du roster sont rapprochés des noms CBS (socle/roster.py).
Niveau « client » : une ligne par client (nom) et agence, sans roster ni objectif ; limité aux
`limite` premiers par encours (le total MICROPOP reste celui de toute la sélection).

COMPTAGES (règle CDG 25/09/2026) : nb clients = noms de clients DISTINCTS ; nb crédits = dossiers.
POTENTIEL fin de mois (coût du risque, migration) : engine.potentiel, « si rien ne change ».

INVARIANTS (testés) : sans filtre, MICROPOP = /par, /provisions, /decaissements, /migrations et
/croissance au centime ; Σ lignes = MICROPOP à chaque niveau.
"""
from __future__ import annotations

import datetime as dt
from collections import defaultdict

from sqlalchemy import func, select

from socle.schema import (DimEmploye, FaitCredit, FaitRemboursementEncaisse, ParamObjectif,
                          ProvisionManuelle, get_session)
from engine.derivation import charger_bareme, taux_provision
from engine.migrations import migrations_sur
from engine.moteur_filtres import filtrer_prets
from engine.moteur_tableau_de_bord import decaissement_periode
from engine.par import _agrege
from engine.potentiel import potentiel_fin_de_mois

NIVEAUX = ("agence", "superviseur", "agent", "client")
ORPHELIN, GELE = "PORTEFEUILLE ORPHELIN", "PORTEFEUILLE GELÉ"

_COLONNES = (FaitCredit.numero_dossier, FaitCredit.numero_client, FaitCredit.agence,
             FaitCredit.agent_credit, FaitCredit.superviseur, FaitCredit.sexe,
             FaitCredit.produit_credit, FaitCredit.est_groupe, FaitCredit.duree,
             FaitCredit.encours, FaitCredit.jours_de_retard, FaitCredit.date_deboursement,
             FaitCredit.montant_debourse, FaitCredit.nom_client, FaitCredit.frequence,
             FaitCredit.date_fin_echeance)


def _arrondi(x: float) -> int:
    """Arrondi commercial (0,5 → supérieur), comme Excel : 333/2 = 166,5 → 167."""
    return int(x + 0.5)


def nb_clients_distincts(prets) -> int:
    """Règle CDG : on compte les NOMS de clients distincts (casse et espaces ignorés)."""
    return len({" ".join((p.nom_client or p.numero_client or "").split()).upper() for p in prets})


def arrete_precedent(s, date_arrete: dt.date) -> dt.date | None:
    """Dernier arrêté chargé AVANT le 1er du mois de l'arrêté (fin du mois précédent)."""
    return s.execute(select(func.max(FaitCredit.date_arrete))
                     .where(FaitCredit.date_arrete < date_arrete.replace(day=1))).scalar()


def tableau_de_bord_credit(date_arrete: dt.date, debut: dt.date | None = None,
                           fin: dt.date | None = None, precedent: dt.date | None = None,
                           niveau: str = "agence", filtres: dict | None = None,
                           db_path="socle/micropop.db", limite: int = 300) -> dict:
    if niveau not in NIVEAUX:
        raise ValueError(f"niveau inconnu : {niveau} (attendu {', '.join(NIVEAUX)})")
    fin = fin or date_arrete
    debut = debut or fin.replace(day=1)
    if debut > fin:
        raise ValueError(f"période de flux inversée : {debut} > {fin}")
    filtres = {k: v for k, v in (filtres or {}).items() if v}
    from socle.agences import agences_non_productives as agences_fermees

    s = get_session(db_path)
    try:
        cur_tous = s.execute(select(*_COLONNES).where(FaitCredit.date_arrete == date_arrete)).all()
        if not cur_tous:
            raise ValueError(f"Aucun prêt pour l'arrêté {date_arrete}. Importer d'abord l'extraction.")
        precedent = precedent or arrete_precedent(s, date_arrete)
        prev_tous = (s.execute(select(*_COLONNES).where(FaitCredit.date_arrete == precedent)).all()
                     if precedent else [])
        bareme = charger_bareme(s, date_arrete)
        manuelles = {pm.agence.strip().upper(): pm.montant for pm in s.execute(
            select(ProvisionManuelle).where(ProvisionManuelle.date_arrete == date_arrete)).scalars()}
        mois = (date_arrete.replace(day=1), date_arrete)
        roster = s.execute(select(DimEmploye.nom, DimEmploye.fonction, DimEmploye.agence).where(
            DimEmploye.date_debut >= mois[0], DimEmploye.date_debut <= mois[1])).all()
        objectifs = s.execute(select(ParamObjectif).where(
            ParamObjectif.date_effet >= mois[0], ParamObjectif.date_effet <= mois[1])).scalars().all()
        fermees = agences_fermees(s)
        R = FaitRemboursementEncaisse
        jour_remb = func.coalesce(R.date_remboursement, R.date_arrete)
        remb_tous = s.execute(select(
            R.numero_dossier, R.numero_client, R.agence, R.agent_credit, R.superviseur,
            R.interets_rembourses, R.capital_rembourse, R.penalites_rembourses,
        ).where(jour_remb >= debut, jour_remb <= fin)).all()
    finally:
        s.close()

    cur = filtrer_prets(cur_tous, **filtres)
    prev = filtrer_prets(prev_tous, **filtres)
    index_prev_tous = {p.numero_dossier: p for p in prev_tous}
    sous_agence = any(k != "agence" for k in filtres)

    # Remboursements de la période, rattachés à la sélection par le n° de dossier.
    from types import SimpleNamespace
    noms = {p.numero_dossier: p.nom_client for p in list(prev_tous) + list(cur_tous)}
    if sous_agence:
        garder = {p.numero_dossier for p in cur} | {p.numero_dossier for p in prev}
        remb_sel = [r for r in remb_tous if r.numero_dossier in garder]
    elif filtres.get("agence"):
        remb_sel = [r for r in remb_tous if (r.agence or "") == filtres["agence"]]
    else:
        remb_sel = list(remb_tous)
    en_retard_m1 = {p.numero_dossier for p in prev_tous if (p.jours_de_retard or 0) > 0}
    remb_sel = [SimpleNamespace(
        numero_dossier=r.numero_dossier, numero_client=r.numero_client, agence=r.agence,
        agent_credit=r.agent_credit, superviseur=r.superviseur,
        nom_client=noms.get(r.numero_dossier), interets=r.interets_rembourses or 0.0,
        capital=r.capital_rembourse or 0.0, penalites=r.penalites_rembourses or 0.0,
        sur_par=r.numero_dossier in en_retard_m1) for r in remb_sel]

    from socle.roster import correspondances, normaliser as maj
    agents_roster = {(maj(n), maj(a)) for n, f, a in roster if f == "agent_credit"}
    sups_roster = {(maj(n), maj(a)) for n, f, a in roster if f == "superviseur"}
    obj = {(maj(o.agent), maj(o.agence)): o for o in objectifs}   # même clé que le roster
    roster_du_mois = bool(roster)
    # nom CBS → nom du roster (identique, ou nom court du fichier OBJECTIF)
    tous = list(cur_tous) + list(prev_tous)
    alias_agents = correspondances(agents_roster, ((p.agent_credit, p.agence) for p in tous))
    alias_sups = correspondances(sups_roster, ((p.superviseur, p.agence) for p in tous))

    def cle(p) -> tuple[str, str]:
        ag = p.agence or "(sans agence)"
        if niveau == "agence":
            return (ag, ag)
        if niveau == "client":
            return (ag, " ".join((p.nom_client or p.numero_client or "?").split()).upper())
        if maj(ag) in fermees:
            return (ag, GELE)
        nom = p.agent_credit if niveau == "agent" else p.superviseur
        ok = alias_agents if niveau == "agent" else alias_sups
        return (ag, nom) if nom and (maj(nom), maj(ag)) in ok else (ag, ORPHELIN)

    p15 = (fin.replace(day=1), min(fin.replace(day=15), fin))

    def ligne(designation, agence, fonction, statut, prets, prets_m1, agents_de_la_ligne, remb=()):
        a = _agrege(prets, designation, fonction)
        m1 = _agrege(prets_m1, designation, fonction)
        d = decaissement_periode(prets, debut, fin)
        d15 = decaissement_periode(prets, max(debut, p15[0]), p15[1]) if debut <= p15[1] else {"nombre": 0}
        prov = sum((p.encours or 0.0) * taux_provision(bareme, p.jours_de_retard or 0)[0] for p in prets)
        compl = 0.0
        if not sous_agence and fonction in ("AGENCE", "FILIALE"):
            agences = {maj(p.agence) for p in prets}
            compl = sum(m for ag, m in manuelles.items() if ag in agences)
        mig = migrations_sur({p.numero_dossier: p for p in prets}, index_prev_tous, bareme) \
            if prev_tous else None
        pot = potentiel_fin_de_mois(prets, index_prev_tous, bareme, date_arrete)
        o = [obj[k] for k in agents_de_la_ligne if k in obj] if objectifs_applicables else []
        obj_nb = sum(x.objectif_decaissement_nombre or 0 for x in o) if o else None
        obj_vol = sum(x.objectif_volume or 0 for x in o) if o else None
        nb_agents = len(agents_de_la_ligne) if roster_du_mois else None
        return {
            "agence": agence, "fonction": fonction, "designation": designation, "statut": statut,
            "nb_agents": nb_agents,
            "p15_objectif": _arrondi(obj_nb / 2) if obj_nb else None,
            "p15": d15["nombre"],
            "objectif_nombre": obj_nb, "decaisse_nombre": d["nombre"],
            "pct_realisation_nombre": (d["nombre"] / obj_nb) if obj_nb else None,
            "productivite": (d["nombre"] / nb_agents) if nb_agents else None,
            "objectif_volume": obj_vol, "decaisse_volume": d["volume"],
            "pct_realisation_volume": (d["volume"] / obj_vol) if obj_vol else None,
            "decaisse_categories": d["par_categorie"],
            "nb_clients": nb_clients_distincts(prets), "nb_credits": a.nb_credits, "encours": a.encours,
            "croissance": (a.encours / m1.encours - 1) if m1.encours else None,
            "par1": a.par1, "par30": a.par30, "par90": a.par90,
            "pct_par1": a.pct_par1, "pct_par30": a.pct_par30, "pct_par90": a.pct_par90,
            "provisions": prov + compl, "complement_daf": compl,
            "cout_du_risque": mig["cout_du_risque"] if mig else None,
            "entree_par_nb": mig["entree_par_nb"] if mig else None,
            "entree_par_montant": mig["entree_par_montant"] if mig else None,
            "migration_vers": mig["migration_vers"] if mig else None,
            "potentiel_cout_du_risque": pot["potentiel_cout_du_risque"],
            "potentiel_migration_nb": pot["potentiel_migration_nb"],
            "potentiel_migration_montant": pot["potentiel_migration_montant"],
            "potentiel_migration_vers": pot["potentiel_migration_vers"],
            "encours_m1": m1.encours, "nb_clients_m1": nb_clients_distincts(prets_m1),
            "nb_credits_m1": m1.nb_credits,
            "interets_encaisses": sum(r.interets for r in remb),
            "capital_rembourse": sum(r.capital for r in remb),
            "penalites_encaissees": sum(r.penalites for r in remb),
            "nb_remboursements": len(remb),
            "recouvre_sur_par": sum(r.capital + r.interets + r.penalites for r in remb if r.sur_par),
        }

    # Objectifs = par AGENT. Un filtre sexe / produit / durée / client découpe le réalisé
    # mais pas l'objectif : les comparer serait trompeur → pas d'objectif, et on le dit.
    objectifs_applicables = not any(k in filtres for k in ("sexe", "produits", "duree", "client"))
    par_portefeuille = any(k in filtres for k in ("agent", "superviseur"))

    def agents_sous(prets, designation=None, agence=None) -> set:
        """Agents du roster rattachés à la ligne (effectif et objectifs)."""
        if designation in (ORPHELIN, GELE) or (niveau == "client" and designation is not None):
            return set()
        if niveau == "agent" and designation is not None:
            k = (maj(designation), maj(agence))
            return {alias_agents[k]} if k in alias_agents else set()
        if par_portefeuille or (niveau == "superviseur" and designation is not None):
            cles = {(maj(p.agent_credit), maj(p.agence)) for p in prets}
            return {alias_agents[k] for k in cles if k in alias_agents}
        agences = {maj(p.agence) for p in prets} if agence is None else {maj(agence)}
        return {k for k in agents_roster if k[1] in agences}

    # Ligne de total : MICROPOP, ou l'agence choisie (le total d'une agence n'est pas « MICROPOP »).
    total_nom = filtres.get("agence") or "MICROPOP"
    lignes = [ligne(total_nom, total_nom, "FILIALE", "actif", cur, prev, agents_sous(cur), remb_sel)]
    nb_lignes_total = None
    if niveau in ("superviseur", "agent") and not roster_du_mois:
        message = (f"Aucun roster importé pour {date_arrete:%m/%Y} : pas de ligne par "
                   f"{niveau} (règle roster). Importer le fichier OBJECTIF du mois.")
    else:
        message = None
        groupes, groupes_m1 = defaultdict(list), defaultdict(list)
        for p in cur:
            groupes[cle(p)].append(p)
        for p in prev:
            groupes_m1[cle(p)].append(p)
        groupes_remb = defaultdict(list)
        for r in remb_sel:
            groupes_remb[cle(r)].append(r)
        for k in groupes_remb:          # une ligne sans encours mais avec des encaissements
            groupes.setdefault(k, [])
        fonction = {"agence": "AGENCE", "superviseur": "SUPERVISEUR", "agent": "AGENT",
                    "client": "CLIENT"}[niveau]
        cles = sorted(groupes)
        if niveau == "client":
            # des milliers de clients : les `limite` plus gros encours ; le reste se filtre
            nb_lignes_total = len(cles)
            cles = sorted(cles, key=lambda k: -sum(p.encours or 0.0 for p in groupes[k]))[:limite]
        for (agence, designation) in cles:
            statut = ("orphelin" if designation == ORPHELIN else
                      "gele" if designation == GELE else "actif")
            prets = groupes[(agence, designation)]
            lignes.append(ligne(designation, agence, fonction, statut, prets,
                                groupes_m1.get((agence, designation), []),
                                agents_sous(prets, designation if niveau != "agence" else None,
                                            agence),
                                groupes_remb.get((agence, designation), [])))

    # Décaissements JOUR PAR JOUR sur la période (graphique « à date »), sélection globale.
    jours: dict[dt.date, list] = defaultdict(lambda: [0, 0.0])
    for p in cur:
        dd = p.date_deboursement
        if dd and debut <= dd <= fin:
            jours[dd][0] += 1
            jours[dd][1] += p.montant_debourse or 0.0
    serie, cumul_nb, cumul_vol = [], 0, 0.0
    jour = debut
    while jour <= fin:
        nb, vol = jours.get(jour, (0, 0.0))
        cumul_nb, cumul_vol = cumul_nb + nb, cumul_vol + vol
        serie.append({"date": jour.isoformat(), "nombre": nb, "volume": vol,
                      "cumul_nombre": cumul_nb, "cumul_volume": cumul_vol})
        jour += dt.timedelta(days=1)

    return {"arrete": date_arrete.isoformat(), "debut": debut.isoformat(), "fin": fin.isoformat(),
            "precedent": precedent.isoformat() if precedent else None, "niveau": niveau,
            "filtres": filtres, "roster_du_mois": roster_du_mois, "message": message,
            "p15_periode": [p15[0].isoformat(), p15[1].isoformat()],
            "nb_prets_selectionnes": len(cur), "lignes": lignes, "decaissements_jour": serie,
            "nb_lignes_total": nb_lignes_total,
            "complement_daf_exclu": sous_agence and bool(manuelles),
            "objectifs_applicables": objectifs_applicables}
