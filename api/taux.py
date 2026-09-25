"""
PopPilot API — consultation des taux de change USD→CDF enregistrés.

  GET /taux?debut=AAAA-MM-JJ&fin=AAAA-MM-JJ            liste CHRONOLOGIQUE (du plus ancien au
                                                       plus récent), bornes incluses, facultatives
  GET /export/tableau/taux?debut=…&fin=…&format=csv|xlsx|pdf   la même liste, mêmes filtres, en fichier

Lecture seule : les taux s'enregistrent par l'import (domaine « taux_change ») ou la page
Configuration. Un taux n'est pas une donnée cloisonnée : tout profil connecté le consulte.
"""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select

from socle.schema import ParamTauxChange, get_session

from auth_supabase import utilisateur_courant

routeur = APIRouter(tags=["taux"])


def _d(s: str | None, nom: str) -> dt.date | None:
    if not s:
        return None
    try:
        return dt.date.fromisoformat(s)
    except ValueError:
        raise HTTPException(422, f"{nom} invalide : {s} (format attendu AAAA-MM-JJ)")


def lister_taux(debut: dt.date | None, fin: dt.date | None, db_path=None) -> list[dict]:
    if debut and fin and debut > fin:
        raise HTTPException(422, f"Période inversée : du {debut} au {fin}.")
    q = select(ParamTauxChange).where(ParamTauxChange.devise_source == "USD",
                                      ParamTauxChange.devise_cible == "CDF")
    if debut:
        q = q.where(ParamTauxChange.date_effet >= debut)
    if fin:
        q = q.where(ParamTauxChange.date_effet <= fin)
    s = get_session(db_path) if db_path else get_session()
    try:
        lignes = s.execute(q.order_by(ParamTauxChange.date_effet.asc())).scalars().all()
    finally:
        s.close()
    return [{"date": r.date_effet.isoformat(), "taux": r.taux} for r in lignes]


@routeur.get("/taux")
def endpoint_taux(debut: str | None = Query(None), fin: str | None = Query(None),
                  user: dict = Depends(utilisateur_courant)):
    d, f = _d(debut, "debut"), _d(fin, "fin")
    taux = lister_taux(d, f)
    return {"debut": debut, "fin": fin, "nombre": len(taux), "taux": taux}


@routeur.get("/export/tableau/taux")
def export_taux(debut: str | None = Query(None), fin: str | None = Query(None),
                format: str = Query("csv"), user: dict = Depends(utilisateur_courant)):
    from export_tableaux import _fichier, _format
    d, f = _d(debut, "debut"), _d(fin, "fin")
    taux = lister_taux(d, f)
    periode = (f"du {d.strftime('%d/%m/%Y') if d else 'premier taux'} "
               f"au {f.strftime('%d/%m/%Y') if f else 'dernier taux'}")
    entete = ["PopPilot — Taux de change USD/CDF", f"Période {periode} ; {len(taux)} taux",
              f"Exporté par {user.get('login') or user.get('email') or '?'} ({user['role']})"]
    nom = f"PopPilot_taux_{debut or 'debut'}_{fin or 'fin'}"
    return _fichier([("Date", "date"), ("Taux USD/CDF", "taux")], taux, entete, nom, _format(format))
