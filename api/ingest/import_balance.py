"""
Import de la balance comptable (Phase 2, Lot 2.1) — CLAUDE.md §38, §42.

Lit la balance (export SAGE 100 → feuille « Balance » du fichier magique) : numéro de compte,
libellé, débit/crédit initial + mouvement, solde net USD. Charge dans fait_balance pour un arrêté.
Idempotent par date_arrete. Le solde net est stocké en devise d'origine (USD ici).
"""
from __future__ import annotations

import datetime as dt
import os

import openpyxl

from socle.schema import FaitBalance, get_session, init_db
from socle import historisation as H


def _f(v):
    if v in (None, ""):
        return 0.0
    try:
        return float(str(v).replace("\xa0", "").replace(" ", "").replace(",", "."))
    except (ValueError, TypeError):
        return 0.0


def importer_balance(path, date_arrete: dt.date, *, feuille="Balance",
                     date_snapshot: dt.date | None = None, devise="USD",
                     db_path="socle/micropop.db"):
    if date_snapshot is None:
        date_snapshot = dt.date.today()
    init_db(db_path)
    s = get_session(db_path)
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb[feuille] if feuille in wb.sheetnames else wb.worksheets[0]

    hdr = [c.value for c in next(ws.iter_rows(min_row=1, max_row=1))]
    if not hdr or "compte" not in str(hdr[0]).lower():
        raise ValueError(f"En-tête inattendu (col1={hdr[0]!r}) — balance requise.")

    purges = H.purge_snapshot(s, "balance", date_arrete)
    acceptees = 0
    for row in ws.iter_rows(min_row=2, values_only=True):
        compte = row[0]
        if compte in (None, ""):
            continue
        c_str = str(compte).strip()
        if not c_str[:1].isdigit():
            continue
        # Solde Net (col L=11) si présent, sinon Débit(7) − Crédit(8). Devise = paramètre.
        if len(row) > 11 and row[11] not in (None, ""):
            solde = _f(row[11])
        else:
            solde = _f(row[6]) - _f(row[7])
        s.add(FaitBalance(
            date_arrete=date_arrete, date_snapshot=date_snapshot,
            numero_compte=c_str, libelle=row[1],
            debit_initial=_f(row[2]), credit_initial=_f(row[3]),
            debit_mvmt=_f(row[4]), credit_mvmt=_f(row[5]),
            solde_net=solde,
            devise=devise,
        ))
        acceptees += 1
    H.enregistrer_import(s, domaine="balance", fichier=os.path.basename(path),
                         date_snapshot=date_snapshot, date_arrete=date_arrete,
                         acceptees=acceptees, rejetees=0, message=f"purge {purges}")
    s.commit()
    s.close()
    return {"acceptees": acceptees, "purges": purges}


if __name__ == "__main__":
    import sys
    print(importer_balance(sys.argv[1], dt.date.fromisoformat(sys.argv[2])))
