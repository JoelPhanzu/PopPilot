"""
Gestion des agences (statut & cycle de vie) — CLAUDE.md note métier.

Une agence est ACTIVE, FERMEE ou SUSPENDUE. Flexible : on peut en ajouter, en fermer, en rouvrir.
Les agences FERMEES ont un portefeuille réel (déclarable BCC) mais AUCUN agent → leur portefeuille
n'est jamais classé « orphelin » ni évalué en performance d'agents.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import select

from socle.schema import DimAgence, get_session, init_db

ACTIVE, FERMEE, SUSPENDUE = "ACTIVE", "FERMEE", "SUSPENDUE"


def enregistrer_agence(session, code, *, nom=None, region=None, statut=ACTIVE,
                       date_ouverture=None, date_fermeture=None, motif=None):
    a = session.execute(select(DimAgence).where(DimAgence.code_agence == code)).scalar_one_or_none()
    if a is None:
        a = DimAgence(code_agence=code)
        session.add(a)
    a.nom = nom or code
    a.region = region
    a.statut = statut
    a.date_ouverture = date_ouverture
    a.date_fermeture = date_fermeture
    a.motif = motif
    session.commit()
    return a


def fermer_agence(session, code, date_fermeture: dt.date, motif=""):
    enregistrer_agence(session, code, statut=FERMEE, date_fermeture=date_fermeture, motif=motif)


def rouvrir_agence(session, code):
    a = session.execute(select(DimAgence).where(DimAgence.code_agence == code)).scalar_one_or_none()
    if a:
        a.statut = ACTIVE
        a.date_fermeture = None
        a.motif = None
        session.commit()


def agences_fermees(session) -> set[str]:
    rows = session.execute(
        select(DimAgence.code_agence).where(DimAgence.statut == FERMEE)
    ).scalars().all()
    return {r.strip().upper() for r in rows}


def seed_agences(db_path="socle/micropop.db"):
    """Enregistre les agences connues. Goma fermée (occupation M23)."""
    init_db(db_path)
    s = get_session(db_path)
    connues = [
        ("AGENCE DE VICTOIRE", ACTIVE, None),
        ("AGENCE OZONE", ACTIVE, None),
        ("AGENCE DE LUBUMBASHI", ACTIVE, None),
        ("AGENCE DE MASINA", ACTIVE, None),
        ("AGENCE DE GOMBE", ACTIVE, None),
        ("AGENCE DE GOMA", FERMEE, "Occupation M23 — agence non fonctionnelle"),
    ]
    for code, statut, motif in connues:
        if statut == FERMEE:
            enregistrer_agence(s, code, statut=FERMEE,
                               date_fermeture=dt.date(2025, 1, 1), motif=motif)
        else:
            enregistrer_agence(s, code, statut=ACTIVE)
    n = s.query(DimAgence).count()
    fermees = agences_fermees(s)
    s.close()
    return {"agences": n, "fermees": sorted(fermees)}


if __name__ == "__main__":
    print(seed_agences())
