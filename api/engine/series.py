"""
Séries temporelles d'indicateurs (module Archives) → table serie_indicateur.

Deux sources, jamais mélangées (colonne `source`) :
  - « import_historique » : historiques passés fournis en Excel (avant PopPilot) ;
  - « calcul_poppilot »   : valeurs recalculées par les MOTEURS VALIDÉS pour un arrêté chargé.

Principe du socle : on ne stocke pas d'indicateur calculé comme FAIT. Ici la série est un
INSTANTANÉ D'AFFICHAGE (courbe d'évolution) : il est toujours recalculable depuis les faits,
et `alimenter_depuis_moteurs` le réécrit à l'identique à chaque appel (idempotent). Pour un
arrêté recalculé, la valeur « calcul_poppilot » fait foi sur celle importée.

Format d'import : une ligne par point — Indicateur | Date | Agence (vide = consolidé) |
Valeur | Unité.
"""
from __future__ import annotations

import datetime as dt
import unicodedata

import openpyxl
from sqlalchemy import select

from socle.schema import FaitCredit, FaitEpargne, SerieIndicateur, get_session, init_db

# Indicateurs calculés par les moteurs, avec leur unité.
CALCULES = {
    "encours_credit": "USD", "par1": "USD", "par30": "USD", "par90": "USD",
    "pct_par30": "%", "nb_credits": "nombre", "provisions": "USD", "epargne": "USD",
}


def _norm(t) -> str:
    return unicodedata.normalize("NFKD", str(t or "")).encode("ascii", "ignore").decode().strip().lower()


def _ecrire(s, indicateur, date_arrete, agence, valeur, unite, source) -> str:
    """Insère ou met à jour UN point. Renvoie 'ajout' / 'maj' / 'garde'."""
    q = select(SerieIndicateur).where(SerieIndicateur.indicateur == indicateur,
                                      SerieIndicateur.date_arrete == date_arrete)
    q = q.where(SerieIndicateur.agence.is_(None) if agence is None else SerieIndicateur.agence == agence)
    ligne = s.execute(q).scalars().first()
    if ligne is None:
        s.add(SerieIndicateur(indicateur=indicateur, date_arrete=date_arrete, agence=agence,
                              valeur=valeur, unite=unite, source=source))
        return "ajout"
    if source == "import_historique" and ligne.source == "calcul_poppilot":
        return "garde"                     # le calcul des moteurs prime sur l'historique importé
    ligne.valeur, ligne.unite, ligne.source = valeur, unite, source
    return "maj"


def alimenter_depuis_moteurs(date_arrete: dt.date, db_path="socle/micropop.db") -> dict:
    """Calcule les indicateurs de l'arrêté avec les moteurs validés et les range en série."""
    from engine.par import calculer_par
    from engine.derivation import deriver_provisions

    points = []
    r = calculer_par(date_arrete, db_path=db_path)
    for ligne, agence in [(r["global"], None)] + [(a, a.designation) for a in r["agences"]]:
        points += [("encours_credit", agence, ligne.encours), ("par1", agence, ligne.par1),
                   ("par30", agence, ligne.par30), ("par90", agence, ligne.par90),
                   ("pct_par30", agence, ligne.pct_par30 * 100), ("nb_credits", agence, ligne.nb_credits)]
    p = deriver_provisions(date_arrete, db_path=db_path)
    points.append(("provisions", None, p["provision_capital_totale"]))
    points += [("provisions", ag, v) for ag, v in p["par_agence"].items() if ag]

    s = get_session(db_path)
    try:
        if s.execute(select(FaitEpargne.id).where(FaitEpargne.date_arrete == date_arrete).limit(1)).first():
            from engine.etats_financiers import taux_change
            from engine.primes_categories import epargne_par_agence
            ep = epargne_par_agence(s, date_arrete, taux_change(s, date_arrete))
            points.append(("epargne", None, sum(ep.values())))
            points += [("epargne", ag, v) for ag, v in ep.items()]
        compte = {"ajout": 0, "maj": 0, "garde": 0}
        for indicateur, agence, valeur in points:
            compte[_ecrire(s, indicateur, date_arrete, agence, float(valeur),
                           CALCULES[indicateur], "calcul_poppilot")] += 1
        s.commit()
    finally:
        s.close()
    return {"arrete": date_arrete.isoformat(), "points": len(points), **compte}


def arretes_non_alimentes(db_path="socle/micropop.db") -> list[str]:
    """Arrêtés crédit chargés dont la série « encours_credit » n'a pas encore été calculée."""
    s = get_session(db_path)
    try:
        credit = set(s.execute(select(FaitCredit.date_arrete).distinct()).scalars())
        faits = set(s.execute(select(SerieIndicateur.date_arrete).where(
            SerieIndicateur.indicateur == "encours_credit",
            SerieIndicateur.source == "calcul_poppilot").distinct()).scalars())
    finally:
        s.close()
    return sorted(d.isoformat() for d in credit - faits)


def _date(v) -> dt.date | None:
    if isinstance(v, dt.datetime):
        return v.date()
    if isinstance(v, dt.date):
        return v
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return dt.datetime.strptime(str(v or "").strip(), fmt).date()
        except ValueError:
            continue
    return None


def importer_series(path, db_path="socle/micropop.db") -> dict:
    """Historiques Excel : Indicateur | Date | Agence | Valeur | Unité (en-tête ligne 1)."""
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.worksheets[0]
    cols, points, erreurs = None, [], []
    for n, row in enumerate(ws.iter_rows(values_only=True), 1):
        if cols is None:
            t = [_norm(c) for c in row]
            if "indicateur" in t and "date" in t and "valeur" in t:
                cols = {k: (t.index(k) if k in t else None) for k in ("indicateur", "date", "agence", "valeur")}
                cols["unite"] = next((i for i, c in enumerate(t) if c.startswith("unit")), None)
            continue
        if not any(c not in (None, "") for c in row):
            continue
        ind = _norm(row[cols["indicateur"]]).replace(" ", "_")
        d = _date(row[cols["date"]])
        try:
            v = float(str(row[cols["valeur"]]).replace("\xa0", "").replace(" ", "").replace(",", "."))
        except (TypeError, ValueError):
            v = None
        if not ind or d is None or v is None:
            erreurs.append(f"ligne {n}")
            continue
        agence = row[cols["agence"]] if cols["agence"] is not None else None
        unite = row[cols["unite"]] if cols["unite"] is not None else None
        points.append((ind, d, str(agence).strip() if agence else None, v,
                       str(unite).strip() if unite else CALCULES.get(ind)))
    if cols is None:
        raise ValueError("En-tête introuvable : attendu Indicateur | Date | Agence | Valeur | Unité.")
    if erreurs:
        raise ValueError("Lignes illisibles (indicateur, date ou valeur) : " + ", ".join(erreurs[:15]))
    init_db(db_path)
    s = get_session(db_path)
    try:
        compte = {"ajout": 0, "maj": 0, "garde": 0}
        for ind, d, ag, v, u in points:
            compte[_ecrire(s, ind, d, ag, v, u, "import_historique")] += 1
        s.commit()
    finally:
        s.close()
    return {"acceptees": len(points), **compte}
