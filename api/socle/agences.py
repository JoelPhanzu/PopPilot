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


# Marqueur « ce champ n'a pas été fourni », à ne pas confondre avec « ce champ vaut None ».
# Indispensable ici : rouvrir une agence doit pouvoir REMETTRE date_fermeture à None,
# ce qu'un simple `if valeur is not None` empêcherait.
_INCHANGE = object()


def enregistrer_agence(session, code, *, nom=_INCHANGE, region=_INCHANGE, statut=_INCHANGE,
                       date_ouverture=_INCHANGE, date_fermeture=_INCHANGE, motif=_INCHANGE):
    """Crée une agence, ou met à jour UNIQUEMENT LES CHAMPS FOURNIS.

    POURQUOI cette précaution : c'était auparavant un upsert intégral, qui réécrivait
    les six champs à leur valeur par défaut à chaque appel. Comme `fermer_agence` ne
    passe que le statut, la date et le motif, fermer une agence EFFAÇAIT son nom, sa
    région et sa date d'ouverture :

        AVANT fermeture : Goma | Nord-Kivu | 2015-03-01
        APRES fermeture : AGENCE DE GOMA | None | None

    Le portefeuille d'une agence fermée reste déclarable à la BCC (note métier Goma) :
    perdre son référentiel au moment précis où on la ferme est le pire moment. Même
    effet sur `seed_agences`, qui remettait date_ouverture à None à chaque exécution.
    """
    a = session.execute(select(DimAgence).where(DimAgence.code_agence == code)).scalar_one_or_none()
    if a is None:
        # À la création seulement, des valeurs de départ : le nom vaut le code tant
        # qu'aucun libellé n'est donné, et une agence naît ACTIVE.
        a = DimAgence(code_agence=code, nom=code, statut=ACTIVE)
        session.add(a)
    for champ, valeur in (("nom", nom), ("region", region), ("statut", statut),
                          ("date_ouverture", date_ouverture),
                          ("date_fermeture", date_fermeture), ("motif", motif)):
        if valeur is not _INCHANGE:
            setattr(a, champ, valeur)
    session.commit()
    return a


def fermer_agence(session, code, date_fermeture: dt.date, motif=""):
    """Ferme une agence SANS toucher à son référentiel (nom, région, date d'ouverture)."""
    return enregistrer_agence(session, code, statut=FERMEE,
                              date_fermeture=date_fermeture, motif=motif)


def rouvrir_agence(session, code):
    """Réouvre une agence existante. Ne crée rien : rouvrir l'inexistant n'a pas de sens."""
    a = session.execute(select(DimAgence).where(DimAgence.code_agence == code)).scalar_one_or_none()
    if a is None:
        return None
    return enregistrer_agence(session, code, statut=ACTIVE, date_fermeture=None, motif=None)


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
