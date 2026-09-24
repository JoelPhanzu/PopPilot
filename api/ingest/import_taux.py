"""
Import des taux USD→CDF depuis un classeur Excel à DEUX colonnes : Date | Taux.

Remplace la saisie jour par jour (page Configuration) : le traitement SAGE convertit chaque
ligne au taux de SON jour, il en faut donc un par jour ouvré.

RÈGLES
- En-tête cherché sur la première feuille : une colonne dont le titre contient « date »,
  une dont le titre contient « taux » (casse et accents indifférents).
- Une date = un taux. Même date deux fois dans le fichier avec deux valeurs → refus.
- Taux ≤ 0 ou illisible, date illisible → refus, avec les numéros de ligne.
- DÉJÀ EN BASE avec une AUTRE valeur → refus, sauf remplacer="oui". Les taux de fin de mois
  déjà saisis servent au FINA, à l'AML et aux conversions (taux en vigueur à l'arrêté) :
  les écraser en silence changerait des rapports déjà produits.
- Même valeur déjà en base → inchangé (l'import est rejouable).
"""
from __future__ import annotations

import datetime as dt
import unicodedata

import openpyxl
from sqlalchemy import select

from socle.schema import ParamTauxChange, get_session, init_db


def _norm(t) -> str:
    return unicodedata.normalize("NFKD", str(t or "")).encode("ascii", "ignore").decode().strip().lower()


def _date(v) -> dt.date | None:
    if isinstance(v, dt.datetime):
        return v.date()
    if isinstance(v, dt.date):
        return v
    texte = str(v or "").strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%y", "%Y-%m-%d %H:%M:%S"):
        try:
            return dt.datetime.strptime(texte, fmt).date()
        except ValueError:
            continue
    return None


def _taux(v) -> float | None:
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v).replace("\xa0", "").replace(" ", "").replace(" ", "")
                     .replace(",", "."))
    except (TypeError, ValueError):
        return None


def lire_taux(path) -> dict[dt.date, float]:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.worksheets[0]
    col_d = col_t = None
    taux: dict[dt.date, float] = {}
    erreurs: list[str] = []
    for n, row in enumerate(ws.iter_rows(values_only=True), 1):
        if col_d is None:
            titres = [_norm(c) for c in row]
            if any("date" in t for t in titres) and any("taux" in t for t in titres):
                col_d = next(i for i, t in enumerate(titres) if "date" in t)
                col_t = next(i for i, t in enumerate(titres) if "taux" in t)
            continue
        if not any(c not in (None, "") for c in row):
            continue
        d, t = _date(row[col_d]), _taux(row[col_t])
        if d is None:
            erreurs.append(f"ligne {n} : date illisible {row[col_d]!r}")
        elif t is None or t <= 0:
            erreurs.append(f"ligne {n} : taux invalide {row[col_t]!r}")
        elif d in taux and abs(taux[d] - t) > 1e-9:
            erreurs.append(f"ligne {n} : {d.isoformat()} en double ({taux[d]} et {t})")
        else:
            taux[d] = t
    if col_d is None:
        raise ValueError("En-tête introuvable : attendu deux colonnes « Date » et « Taux ».")
    if erreurs:
        raise ValueError("Fichier de taux refusé — " + " ; ".join(erreurs[:10])
                         + (f" (+{len(erreurs) - 10} autres)" if len(erreurs) > 10 else ""))
    if not taux:
        raise ValueError("Aucun taux sous l'en-tête Date | Taux.")
    return taux


def importer_taux(path, remplacer: str | None = None, db_path="socle/micropop.db") -> dict:
    taux = lire_taux(path)
    ecraser = _norm(remplacer) in ("oui", "o", "true", "1", "yes")
    init_db(db_path)
    s = get_session(db_path)
    try:
        existants = {r.date_effet: r for r in s.execute(
            select(ParamTauxChange).where(ParamTauxChange.devise_source == "USD",
                                          ParamTauxChange.devise_cible == "CDF",
                                          ParamTauxChange.date_effet.in_(list(taux)))
        ).scalars()}
        conflits = sorted(d for d, r in existants.items() if abs(r.taux - taux[d]) > 1e-9)
        if conflits and not ecraser:
            detail = ", ".join(f"{d.isoformat()} (base {existants[d].taux} / fichier {taux[d]})"
                               for d in conflits[:8])
            raise ValueError(
                f"{len(conflits)} date(s) déjà en base avec un AUTRE taux : {detail}. "
                "Rien n'a été importé. Renvoyer avec remplacer = « oui » pour les écraser "
                "(attention : FINA, AML et conversions de ces dates changeront).")
        ajoutes = remplaces = 0
        for d, t in taux.items():
            r = existants.get(d)
            if r is None:
                s.add(ParamTauxChange(date_effet=d, devise_source="USD", devise_cible="CDF", taux=t))
                ajoutes += 1
            elif abs(r.taux - t) > 1e-9:
                r.taux = t
                remplaces += 1
        s.commit()
    finally:
        s.close()
    jours = sorted(taux)
    return {"acceptees": len(taux), "ajoutes": ajoutes, "remplaces": remplaces,
            "inchanges": len(taux) - ajoutes - remplaces,
            "du": jours[0].isoformat(), "au": jours[-1].isoformat()}
