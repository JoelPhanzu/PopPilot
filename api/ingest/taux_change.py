"""
Saisie manuelle du taux de change USD→CDF par période (FINA & conversions).
Le taux de clôture BCC change chaque mois → l'utilisateur le saisit, il n'est jamais figé.
Historisé par date d'effet (§18.4).
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import select

from socle.schema import ParamTauxChange, get_session, init_db


def saisir_taux(date_effet: dt.date, taux: float, *, db_path="socle/micropop.db"):
    """Enregistre/actualise le taux USD→CDF à une date d'effet."""
    init_db(db_path)
    s = get_session(db_path)
    row = s.execute(
        select(ParamTauxChange).where(ParamTauxChange.date_effet == date_effet,
                                      ParamTauxChange.devise_source == "USD")
    ).scalar_one_or_none()
    if row is None:
        row = ParamTauxChange(date_effet=date_effet, devise_source="USD", devise_cible="CDF")
        s.add(row)
    row.taux = taux
    s.commit()
    s.close()
    return {"date_effet": date_effet, "taux": taux}


def taux_en_vigueur(date_arrete: dt.date, db_path="socle/micropop.db"):
    s = get_session(db_path)
    t = s.execute(
        select(ParamTauxChange.taux).where(ParamTauxChange.date_effet <= date_arrete)
        .order_by(ParamTauxChange.date_effet.desc())
    ).scalars().first()
    s.close()
    return t


if __name__ == "__main__":
    import sys
    print(saisir_taux(dt.date.fromisoformat(sys.argv[1]), float(sys.argv[2])))
