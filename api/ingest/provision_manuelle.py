"""
Saisie des provisions manuelles par agence (décision comptable + DAF) — note métier Goma.

Le 1 % cumulé de Goma n'est PAS calculé par l'outil : les comptables le prélèvent manuellement
avec l'accord du DAF. Ici on ENREGISTRE le montant validé, tracé, pour un arrêté donné.
Ce montant remplace le barème automatique pour l'agence (cf. engine/derivation.py).
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import select

from socle.schema import ProvisionManuelle, get_session, init_db


def saisir_provision_manuelle(date_arrete: dt.date, agence: str, montant: float,
                              *, note: str = "", saisi_par: str = "",
                              db_path="socle/micropop.db"):
    """Enregistre (ou met à jour) la provision manuelle d'une agence pour un arrêté.
    Idempotent sur (date_arrete, agence)."""
    init_db(db_path)
    s = get_session(db_path)
    pm = s.execute(
        select(ProvisionManuelle).where(
            ProvisionManuelle.date_arrete == date_arrete,
            ProvisionManuelle.agence == agence)
    ).scalar_one_or_none()
    if pm is None:
        pm = ProvisionManuelle(date_arrete=date_arrete, agence=agence)
        s.add(pm)
    pm.montant = montant
    pm.note = note
    pm.saisi_par = saisi_par
    pm.horodatage = dt.datetime.now()
    s.commit()
    s.close()
    return {"date_arrete": date_arrete, "agence": agence, "montant": montant, "note": note}


def lister_provisions_manuelles(date_arrete: dt.date, db_path="socle/micropop.db"):
    s = get_session(db_path)
    rows = s.execute(
        select(ProvisionManuelle).where(ProvisionManuelle.date_arrete == date_arrete)
    ).scalars().all()
    out = [{"agence": r.agence, "montant": r.montant, "note": r.note,
            "saisi_par": r.saisi_par, "horodatage": r.horodatage} for r in rows]
    s.close()
    return out


if __name__ == "__main__":
    # Exemple : Goma, mai 2026, ~16 mois de fermeture → 16 % de 1 453 955,88
    r = saisir_provision_manuelle(
        dt.date(2026, 5, 30), "AGENCE DE GOMA", 1453955.88 * 0.16,
        note="16 % — 1 % cumulé/mois depuis fermeture, validé DAF", saisi_par="demo")
    print(r)
