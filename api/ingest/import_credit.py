"""
Import de l'extraction crédit (Lot 1.1) — CLAUDE.md §4, Livrable 3 (contrôles I-*).

Lit les 32 colonnes brutes du SIG (A→AF), valide, charge dans fait_credit pour une date_arrete.
- Idempotent : purge le snapshot de la date_arrete avant de recharger (§23, règle I-4).
- date_arrete explicite (jamais TODAY, règle I-3). date_snapshot = date d'import.
- est_groupe = (produit == 'LISANGA') (§45).
- Ne stocke QUE le brut ; provisions/PAR sont recalculés par le moteur (engine/).
"""
from __future__ import annotations

import datetime as dt
import os

import openpyxl

from socle.schema import FaitCredit, get_session, init_db
from socle import historisation as H

# position → attribut (les 32 colonnes SIG, ordre A→AF)
COLONNES = [
    "agence", "numero_dossier", "numero_client", "nom_client", "produit_credit",
    "montant_debourse", "date_deboursement", "date_fin_echeance", "agent_credit",
    "superviseur", "id_groupe", "nom_groupe", "femme", "homme", "duree",
    "taux_interet", "frequence", "encours", "interets", "interets_retard",
    "penalites", "jours_de_retard", "capital_retard", "impayes", "garantie",
    "tr_1_7", "tr_8_30", "tr_31_60", "tr_61_90", "tr_91_180", "tr_181_360", "tr_361_plus",
]


def _to_date(v):
    if isinstance(v, dt.datetime):
        return v.date()
    if isinstance(v, dt.date):
        return v
    if isinstance(v, str) and v.strip():
        for fmt in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d", "%d-%m-%Y"):
            try:
                return dt.datetime.strptime(v.strip(), fmt).date()
            except ValueError:
                continue
    return None


def _to_float(v):
    if v in (None, ""):
        return 0.0
    try:
        return float(str(v).replace(",", ".").replace("\xa0", "").replace(" ", ""))
    except ValueError:
        return 0.0


def _to_int(v):
    return int(round(_to_float(v)))


def _ouvrir(path):
    """Ouvre .xlsx ; si .xls trompeur (en réalité xlsx), copie et rouvre (règle I-1)."""
    try:
        return openpyxl.load_workbook(path, read_only=True, data_only=True)
    except Exception:
        tmp = "/tmp/_reopen.xlsx"
        import shutil
        shutil.copy(path, tmp)
        return openpyxl.load_workbook(tmp, read_only=True, data_only=True)


def importer_credit(path, date_arrete: dt.date, *, feuille="Worksheet",
                    date_snapshot: dt.date | None = None, db_path="socle/micropop.db"):
    if date_snapshot is None:
        date_snapshot = dt.date.today()
    init_db(db_path)
    s = get_session(db_path)

    wb = _ouvrir(path)
    ws = wb[feuille] if feuille in wb.sheetnames else wb.worksheets[0]

    # en-tête : vérifier qu'on est bien sur l'extraction 32 colonnes (règle I-2)
    hdr = [c.value for c in next(ws.iter_rows(min_row=1, max_row=1))]
    if hdr[1] is None or "dossier" not in str(hdr[1]).lower():
        raise ValueError(f"En-tête inattendu (col 2 = {hdr[1]!r}) — extraction crédit A→AF requise.")

    # idempotence (règle I-4)
    purges = H.purge_snapshot(s, "credit", date_arrete)

    acceptees = rejetees = 0
    for row in ws.iter_rows(min_row=2, values_only=True):
        if row[1] in (None, ""):          # pas de numéro dossier → ligne vide
            continue
        d = dict(zip(COLONNES, row))
        try:
            fc = FaitCredit(
                date_arrete=date_arrete, date_snapshot=date_snapshot,
                numero_dossier=str(d["numero_dossier"]).strip(),
                numero_client=str(d["numero_client"] or "").strip(),
                nom_client=d["nom_client"],
                produit_credit=d["produit_credit"],
                est_groupe=("LISANGA" in str(d["produit_credit"] or "").upper()),
                agence=str(d["agence"] or "").strip(),
                agent_credit=str(d["agent_credit"] or "").strip(),
                superviseur=str(d["superviseur"] or "").strip(),
                id_groupe=d["id_groupe"], nom_groupe=d["nom_groupe"],
                sexe=("F" if _to_float(d["femme"]) else "H"),
                montant_debourse=_to_float(d["montant_debourse"]),
                date_deboursement=_to_date(d["date_deboursement"]),
                date_fin_echeance=_to_date(d["date_fin_echeance"]),
                duree=_to_float(d["duree"]), taux_interet=_to_float(d["taux_interet"]),
                frequence=str(d["frequence"] or ""),
                encours=_to_float(d["encours"]),
                interets=_to_float(d["interets"]),
                interets_retard=_to_float(d["interets_retard"]),
                penalites=_to_float(d["penalites"]),
                jours_de_retard=_to_int(d["jours_de_retard"]),
                capital_retard=_to_float(d["capital_retard"]),
                impayes=_to_float(d["impayes"]), garantie=_to_float(d["garantie"]),
                tr_1_7=_to_float(d["tr_1_7"]), tr_8_30=_to_float(d["tr_8_30"]),
                tr_31_60=_to_float(d["tr_31_60"]), tr_61_90=_to_float(d["tr_61_90"]),
                tr_91_180=_to_float(d["tr_91_180"]), tr_181_360=_to_float(d["tr_181_360"]),
                tr_361_plus=_to_float(d["tr_361_plus"]),
                devise="USD",
            )
            s.add(fc)
            acceptees += 1
        except Exception:
            rejetees += 1
    H.enregistrer_import(s, domaine="credit", fichier=os.path.basename(path),
                         date_snapshot=date_snapshot, date_arrete=date_arrete,
                         acceptees=acceptees, rejetees=rejetees,
                         message=f"purge {purges} lignes")
    s.commit()
    s.close()
    return {"acceptees": acceptees, "rejetees": rejetees, "purges": purges}


if __name__ == "__main__":
    import sys
    path = sys.argv[1]
    arrete = dt.date.fromisoformat(sys.argv[2]) if len(sys.argv) > 2 else dt.date(2026, 5, 31)
    print(importer_credit(path, arrete))
