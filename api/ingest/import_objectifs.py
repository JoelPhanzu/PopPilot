"""
Import du roster mensuel + objectifs (Lot 1.6 amont) — CLAUDE.md §5, §15.3, §18.2.

Le fichier OBJECTIF est DOUBLE source :
  - dim_employe : la liste officielle des agents/superviseurs actifs (→ détection orphelins).
  - param_objectif : leurs objectifs (décaissement nombre, volume, portefeuille, PAR).
Versionné à date d'effet : le roster de mai ne s'applique qu'aux calculs de mai (§18.4).
"""
from __future__ import annotations

import datetime as dt

import openpyxl

from socle.schema import DimEmploye, ParamObjectif, get_session, init_db
from socle import historisation as _noop  # noqa


def _f(v):
    if v in (None, ""):
        return 0.0
    try:
        return float(str(v).replace(",", ".").replace("\xa0", "").replace(" ", ""))
    except ValueError:
        return 0.0


def importer_objectifs(path, date_effet: dt.date, db_path="socle/micropop.db"):
    init_db(db_path)
    s = get_session(db_path)
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb["OBJECTIF"] if "OBJECTIF" in wb.sheetnames else wb.worksheets[0]

    # purge du roster + objectifs de cette date d'effet (idempotence)
    s.query(DimEmploye).filter(DimEmploye.date_debut == date_effet).delete()
    s.query(ParamObjectif).filter(ParamObjectif.date_effet == date_effet).delete()

    agents = superviseurs = 0
    superviseurs_vus = set()
    for row in ws.iter_rows(min_row=2, values_only=True):
        agence, superviseur, agent = row[0], row[1], row[2]
        if not agent:
            continue
        agence = str(agence).strip()
        agent = str(agent).strip()
        superviseur = str(superviseur).strip() if superviseur else ""

        # agent de crédit
        s.add(DimEmploye(nom=agent, fonction="agent_credit", agence=agence,
                         date_debut=date_effet, date_fin=None))
        agents += 1
        # superviseur (une fois par nom+agence)
        if superviseur and (superviseur, agence) not in superviseurs_vus:
            s.add(DimEmploye(nom=superviseur, fonction="superviseur", agence=agence,
                             date_debut=date_effet, date_fin=None))
            superviseurs_vus.add((superviseur, agence))
            superviseurs += 1
        # objectifs de l'agent
        s.add(ParamObjectif(
            date_effet=date_effet, agence=agence, agent=agent,
            objectif_decaissement_nombre=_f(row[3]),   # #NOMBRE A DECAISSE
            objectif_volume=_f(row[4]),                # VOLUME
            objectif_portefeuille=_f(row[5]),          # PORTEFEUILLE (volume)
            objectif_par=_f(row[7]),                   # PAR
        ))
    s.commit()
    n_obj = s.query(ParamObjectif).filter(ParamObjectif.date_effet == date_effet).count()
    s.close()
    return {"agents": agents, "superviseurs": superviseurs, "objectifs": n_obj}


if __name__ == "__main__":
    import sys
    path = sys.argv[1]
    eff = dt.date.fromisoformat(sys.argv[2]) if len(sys.argv) > 2 else dt.date(2026, 5, 1)
    print(importer_objectifs(path, eff))
