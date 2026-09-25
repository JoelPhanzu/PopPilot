"""
Import des taux USD→CDF depuis un fichier Date | Taux (.xlsx, .xlsm, .xls ou .csv).

Remplace la saisie jour par jour (page Configuration) : le traitement SAGE convertit chaque
ligne au taux de SON jour, il en faut donc un par jour ouvré.

FORMATS ACCEPTÉS
- Fichier à deux colonnes « Date » et « Taux » ;
- l'extraction BRUTE du site de la BCC (« cours-de-change.xlsx » : Date | USD/CDF | EUR/CDF…) :
  la colonne « USD/CDF » est prise comme taux, les autres devises sont ignorées.
- Virgule ou point décimal, espaces de milliers, dates JJ/MM/AAAA ou AAAA-MM-JJ.

RÈGLES
- Une date = un taux. Même date deux fois dans le fichier avec deux valeurs → refus.
- Taux ≤ 0 ou illisible, date illisible → refus, avec les numéros de ligne.
- Date DÉJÀ EN BASE avec une AUTRE valeur (conflit) — choix explicite de l'utilisateur :
    remplacer = OUI → le taux du fichier REMPLACE celui de la base (le fichier de la BCC fait foi) ;
    remplacer = NON → les dates NOUVELLES sont ajoutées, les taux existants sont CONSERVÉS ;
    rien          → refus avec la liste des conflits : on ne choisit pas à la place de
                    l'utilisateur (ces taux servent au FINA, à l'AML, aux conversions).
- Même valeur déjà en base (à 1e-6 près) → inchangé (l'import est rejouable).
"""
from __future__ import annotations

import datetime as dt
import unicodedata

from sqlalchemy import select

from socle.schema import ParamTauxChange, get_session, init_db

OUI = {"oui", "o", "yes", "y", "true", "1", "remplacer", "ecraser"}
NON = {"non", "n", "no", "false", "0", "conserver", "garder"}
TOLERANCE = 1e-6


def _norm(t) -> str:
    return unicodedata.normalize("NFKD", str(t or "")).encode("ascii", "ignore").decode().strip().lower()


def _date(v) -> dt.date | None:
    if isinstance(v, dt.datetime):
        return v.date()
    if isinstance(v, dt.date):
        return v
    if isinstance(v, (int, float)) and 20000 < v < 80000:        # numéro de série Excel (.xls)
        return dt.date(1899, 12, 30) + dt.timedelta(days=int(v))
    texte = str(v or "").strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%y", "%Y-%m-%d %H:%M:%S",
                "%d.%m.%Y", "%Y/%m/%d"):
        try:
            return dt.datetime.strptime(texte, fmt).date()
        except ValueError:
            continue
    return None


def _taux(v) -> float | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    t = str(v or "").replace("\xa0", "").replace(" ", "").replace(" ", "").strip()
    if not t:
        return None
    if "," in t and "." in t:                                       # 2.263,57 ou 2,263.57
        t = t.replace(".", "").replace(",", ".") if t.rfind(",") > t.rfind(".") else t.replace(",", "")
    else:
        t = t.replace(",", ".")
    try:
        return float(t)
    except ValueError:
        return None


def _colonnes(titres: list[str]) -> tuple[int, int] | None:
    """(colonne date, colonne taux) : « Taux », sinon « USD/CDF » (extraction BCC)."""
    if not any(t == "date" or t.startswith("date") for t in titres):
        return None
    col_d = next(i for i, t in enumerate(titres) if t == "date" or t.startswith("date"))
    for critere in (lambda t: "taux" in t, lambda t: t.replace(" ", "") in ("usd/cdf", "usdcdf", "usd-cdf")):
        for i, t in enumerate(titres):
            if i != col_d and critere(t):
                return col_d, i
    return None


def lire_taux(path) -> dict[dt.date, float]:
    from engine.import_compte_resultat_agence import lire_lignes
    rows = lire_lignes(path, feuille="")          # première feuille
    cols = None
    taux: dict[dt.date, float] = {}
    erreurs: list[str] = []
    for n, row in enumerate(rows, 1):
        if cols is None:
            cols = _colonnes([_norm(c) for c in row])
            continue
        if not any(c not in (None, "") for c in row):
            continue
        col_d, col_t = cols
        vd = row[col_d] if len(row) > col_d else None
        vt = row[col_t] if len(row) > col_t else None
        d, t = _date(vd), _taux(vt)
        if d is None:
            erreurs.append(f"ligne {n} : date illisible {vd!r}")
        elif t is None or t <= 0:
            erreurs.append(f"ligne {n} : taux invalide {vt!r}")
        elif d in taux and abs(taux[d] - t) > TOLERANCE:
            erreurs.append(f"ligne {n} : {d.isoformat()} en double ({taux[d]} et {t})")
        else:
            taux[d] = t
    if cols is None:
        raise ValueError("En-tête introuvable : attendu une colonne « Date » et une colonne "
                         "« Taux » (ou « USD/CDF » pour l'extraction du site de la BCC).")
    if erreurs:
        raise ValueError("Fichier de taux refusé — " + " ; ".join(erreurs[:10])
                         + (f" (+{len(erreurs) - 10} autres)" if len(erreurs) > 10 else ""))
    if not taux:
        raise ValueError("Aucun taux sous l'en-tête Date | Taux.")
    return taux


def importer_taux(path, remplacer: str | None = None, db_path="socle/micropop.db") -> dict:
    taux = lire_taux(path)
    choix = _norm(remplacer)
    if choix and choix not in OUI | NON:
        raise ValueError(f"Remplacer = « {remplacer} » : répondre OUI (écraser les taux existants) "
                         "ou NON (importer sans écraser).")
    init_db(db_path)
    s = get_session(db_path)
    try:
        existants = {r.date_effet: r for r in s.execute(
            select(ParamTauxChange).where(ParamTauxChange.devise_source == "USD",
                                          ParamTauxChange.devise_cible == "CDF",
                                          ParamTauxChange.date_effet.in_(list(taux)))
        ).scalars()}
        conflits = sorted(d for d, r in existants.items() if abs(r.taux - taux[d]) > TOLERANCE)
        if conflits and not choix:
            detail = ", ".join(f"{d.strftime('%d/%m/%Y')} (base {existants[d].taux:g} / fichier "
                               f"{taux[d]:g})" for d in conflits[:8])
            raise ValueError(
                f"{len(conflits)} date(s) déjà en base avec un AUTRE taux : {detail}"
                + (f" (+{len(conflits) - 8} autres)" if len(conflits) > 8 else "")
                + ". Rien n'a été importé. Remplacer = OUI pour écraser ces taux par ceux du "
                "fichier, ou NON pour importer les nouvelles dates en gardant les taux existants.")
        ecraser = choix in OUI
        ajoutes = remplaces = conserves = 0
        for d, t in taux.items():
            r = existants.get(d)
            if r is None:
                s.add(ParamTauxChange(date_effet=d, devise_source="USD", devise_cible="CDF", taux=t))
                ajoutes += 1
            elif abs(r.taux - t) > TOLERANCE:
                if ecraser:
                    r.taux = t
                    remplaces += 1
                else:
                    conserves += 1
        s.commit()
    finally:
        s.close()
    jours = sorted(taux)
    return {"acceptees": len(taux), "ajoutes": ajoutes, "remplaces": remplaces,
            "conserves": conserves,
            "inchanges": len(taux) - ajoutes - remplaces - conserves,
            "du": jours[0].isoformat(), "au": jours[-1].isoformat()}
