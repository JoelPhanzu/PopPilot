"""
PopPilot API — Eljo Smart (messagerie) : POST /eljo, GET /eljo/historique.

Eljo (engine/eljo_smart.py) comprend la question ; CE module fournit `resoudre_valeur`,
qui appelle les MOTEURS VALIDÉS — jamais un chiffre inventé ni estimé :

  par          engine.par.calculer_par            PAR30 (+ PAR1/PAR90 en détail)
  encours      engine.par.calculer_par            encours de crédit
  provision    engine.derivation.deriver_provisions  (refusé à un rôle AGENCE, comme /provisions)
  decaissement engine.decaissement.decaissements  volume du 1er du mois à l'arrêté
  epargne      engine.epargne.synthese_epargne / engine.primes_categories.epargne_par_agence
  resultat     compte_resultat_agence (fichier du CDG importé)

Date : « mai 2026 » → l'arrêté du mois présent dans la base pour CE domaine ; sans mois →
le plus récent. Aucun arrêté pour le mois demandé → réponse « indisponible », pas un voisin.

Cloisonnement : engine/eljo_smart ramène un rôle AGENCE à son agence et refuse les autres ;
ce module ne renvoie jamais un agrégat institution à un rôle AGENCE.
Traçabilité : chaque échange est écrit dans eljo_conversation (question, intention, réponse,
valeur exacte).
"""
from __future__ import annotations

import calendar
import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from socle.schema import (BASE_PAR_DEFAUT, CompteResultatAgence, EljoConversation, FaitCredit,
                          FaitEpargne, get_session)
from engine.eljo_smart import INTENTIONS, repondre

from auth_supabase import ROLES_ACCES_TOTAL, exiger_role, utilisateur_courant

routeur = APIRouter(tags=["eljo"])

# Base visée par les moteurs : celle de la plateforme (Supabase si DATABASE_URL). Les tests
# la remplacent par un fichier SQLite — jamais l'inverse.
BASE = BASE_PAR_DEFAUT

_DOMAINE = {"par": FaitCredit, "encours": FaitCredit, "provision": FaitCredit,
            "decaissement": FaitCredit, "epargne": FaitEpargne, "resultat": CompteResultatAgence}


def _arrete(intention: str, date) -> dt.date:
    """Arrêté présent en base pour ce domaine : dans le mois demandé, ou le plus récent."""
    table = _DOMAINE[intention]
    q = select(func.max(table.date_arrete))
    if date:
        annee, mois = date
        q = q.where(table.date_arrete >= dt.date(annee, mois, 1),
                    table.date_arrete <= dt.date(annee, mois, calendar.monthrange(annee, mois)[1]))
    s = get_session(BASE)
    try:
        d = s.execute(q).scalar()
    finally:
        s.close()
    if d is None:
        quand = f"{date[1]:02d}/{date[0]}" if date else "aucune période"
        raise ValueError(f"aucune donnée « {INTENTIONS[intention]['libelle']} » importée pour {quand}")
    return d


def _agence_complete(demandee: str | None, connues) -> str | None:
    """« OZONE » (mot de la question) → « AGENCE OZONE » (libellé des données)."""
    if not demandee:
        return None
    for nom in connues:
        if nom and (nom.strip().upper() == demandee.strip().upper()
                    or demandee.strip().upper() in nom.upper().split()):
            return nom
    raise ValueError(f"agence « {demandee} » introuvable dans les données de cette période")


def resoudre_valeur(intention: str, date, agence: str | None, user: dict):
    from engine.par import calculer_par
    total = user["role"] in ROLES_ACCES_TOTAL
    d = _arrete(intention, date)
    detail = {"arrete": d.isoformat()}

    if intention in ("par", "encours"):
        r = calculer_par(d, db_path=BASE)
        if agence:
            nom = _agence_complete(agence, [a.designation for a in r["agences"]])
            l = next(a for a in r["agences"] if a.designation == nom)
        else:
            l = r["global"]
        detail.update({"perimetre": l.designation, "encours": l.encours, "par1": l.par1,
                       "par30": l.par30, "par90": l.par90, "pct_par1": l.pct_par1 * 100,
                       "pct_par30": l.pct_par30 * 100, "pct_par90": l.pct_par90 * 100})
        if intention == "encours":
            return l.encours, {**detail, "nb_credits": l.nb_credits}
        detail["mesure"] = "PAR30 (retard > 30 jours), montant USD"
        return l.par30, detail

    if intention == "provision":
        if not total:
            raise ValueError("les provisions sont un agrégat institution, réservé à la Direction, "
                             "au CDG et à l'Audit")
        from engine.derivation import deriver_provisions
        p = deriver_provisions(d, db_path=BASE)
        if agence:
            nom = _agence_complete(agence, p["par_agence"])
            return p["par_agence"][nom], {**detail, "perimetre": nom}
        return p["provision_capital_totale"], {**detail, "perimetre": "MICROPOP"}

    if intention == "decaissement":
        from engine.decaissement import decaissements
        r = decaissements(d, db_path=BASE)
        if agence:
            nom = _agence_complete(agence, r["par_agence"])
            v = r["par_agence"][nom]
            return v["volume"], {**detail, "perimetre": nom, "nombre": v["nombre"]}
        return r["global"]["volume"], {**detail, "perimetre": "MICROPOP",
                                       "nombre": r["global"]["nombre"]}

    if intention == "epargne":
        from engine.etats_financiers import taux_change
        from engine.primes_categories import epargne_par_agence
        s = get_session(BASE)
        try:
            par_ag = epargne_par_agence(s, d, taux_change(s, d))
        finally:
            s.close()
        if agence:
            nom = _agence_complete(agence, par_ag)
            return par_ag[nom], {**detail, "perimetre": nom, "devise": "USD"}
        return sum(par_ag.values()), {**detail, "perimetre": "MICROPOP", "devise": "USD"}

    if intention == "resultat":
        s = get_session(BASE)
        try:
            lignes = s.execute(select(CompteResultatAgence.poste, CompteResultatAgence.agence,
                                      CompteResultatAgence.montant)
                               .where(CompteResultatAgence.date_arrete == d)).all()
        finally:
            s.close()
        res = {ag: m for poste, ag, m in lignes
               if "RESULTAT" in poste.upper() and "COMPTABLE" in poste.upper()}
        if agence:
            nom = _agence_complete(agence, res)
            return res[nom], {**detail, "perimetre": nom}
        return sum(res.values()), {**detail, "perimetre": "MICROPOP"}

    raise ValueError(f"indicateur non branché : {intention}")


class Question(BaseModel):
    question: str = Field(..., min_length=2, max_length=500)


@routeur.post("/eljo")
def endpoint_eljo(q: Question, user: dict = Depends(utilisateur_courant)):
    exiger_role(user, ROLES_ACCES_TOTAL | {"AGENCE"})
    r = repondre(q.question, user, resoudre_valeur)
    valeur = r.get("valeur")
    s = get_session(BASE)
    try:
        s.add(EljoConversation(
            login=user["login"], role=user["role"], agence=user.get("agence"),
            question=q.question, intention=(r.get("comprehension") or {}).get("intention"),
            reponse=r["reponse"], valeur=valeur if isinstance(valeur, (int, float)) else None,
            horodatage=dt.datetime.now()))
        s.commit()
    finally:
        s.close()
    return r


@routeur.get("/eljo/historique")
def endpoint_historique(limite: int = Query(30, ge=1, le=200),
                        user: dict = Depends(utilisateur_courant)):
    """Les échanges de l'utilisateur lui-même (du plus ancien au plus récent)."""
    exiger_role(user, ROLES_ACCES_TOTAL | {"AGENCE"})
    s = get_session(BASE)
    try:
        lignes = s.execute(select(EljoConversation).where(EljoConversation.login == user["login"])
                           .order_by(EljoConversation.id.desc()).limit(limite)).scalars().all()
    finally:
        s.close()
    return {"echanges": [{"question": l.question, "reponse": l.reponse, "valeur": l.valeur,
                          "intention": l.intention,
                          "horodatage": l.horodatage.isoformat() if l.horodatage else None}
                         for l in reversed(lignes)]}
