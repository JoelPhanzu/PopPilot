"""
Import de l'inventaire dépôt / épargne (Phase Épargne) — CLAUDE.md §51.

CSV séparateur ';', encodage UTF-8 BOM, décimales à la virgule. ~170 000 comptes.
Classe chaque compte : type_depot (a_vue / a_terme / obligatoire) et est_groupe.
Idempotent par date_arrete.

Règle produits (confirmée CDG) :
  - à terme     : Pop Monnaie A Terme, EducaPop A Terme
  - obligatoire : Pop Monnaie Nantie, Caution Groupes
  - à vue       : tout le reste
Groupe (§51.3) : Transitoire Groupe (id 15,17) + Caution Groupes (id 20).
"""
from __future__ import annotations

import csv
import datetime as dt
import os

from socle.schema import FaitEpargne, get_session, init_db
from socle import historisation as H

csv.field_size_limit(10_000_000)


def _classer_type(libelle: str) -> str:
    l = (libelle or "").upper()
    if "A TERME" in l or "À TERME" in l:
        return "a_terme"
    if "NANTIE" in l or "CAUTION" in l:
        return "obligatoire"
    return "a_vue"


def _est_groupe(id_prod: str, libelle: str) -> bool:
    l = (libelle or "").upper()
    return "GROUPE" in l or str(id_prod) in ("15", "17", "20")


def _f(v):
    if v in (None, ""):
        return 0.0
    try:
        return float(str(v).replace(",", ".").replace("\xa0", "").replace(" ", ""))
    except (ValueError, TypeError):
        return 0.0


def _d(v):
    if not v:
        return None
    for fmt in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(str(v).strip(), fmt).date()
        except ValueError:
            continue
    return None


def importer_epargne(path, date_arrete: dt.date, *, date_snapshot=None,
                     db_path="socle/micropop.db", batch=5000):
    if date_snapshot is None:
        date_snapshot = dt.date.today()
    init_db(db_path)
    s = get_session(db_path)
    purges = H.purge_snapshot(s, "epargne", date_arrete)

    acceptees = 0
    with open(path, encoding="utf-8-sig", errors="replace") as fh:
        r = csv.DictReader(fh, delimiter=";")
        for row in r:
            if not row.get("id_cpte"):
                continue
            libelle = row.get("libel")
            s.add(FaitEpargne(
                date_arrete=date_arrete, date_snapshot=date_snapshot,
                id_compte=str(row.get("id_cpte")).strip(),
                num_complet_cpte=row.get("num_complet_cpte"),
                id_client=str(row.get("id_client") or "").strip(),
                id_prod=str(row.get("id_prod") or "").strip(),
                libelle_produit=libelle,
                agence=row.get("libelle_niveau"),
                devise=row.get("devise"),
                solde_actuel=_f(row.get("solde_actuel")),
                solde_debut=_f(row.get("solde_debut")),
                solde_fin=_f(row.get("solde_fin")),
                montant_depot=_f(row.get("montant_depot")),
                montant_retrait=_f(row.get("montant_retrait")),
                sexe=row.get("sexe"),
                secteur_activite=row.get("secteur_activite"),
                ville=row.get("ville"),
                date_ouverture=_d(row.get("date_ouvert")),
                est_groupe=_est_groupe(row.get("id_prod"), libelle),
                type_depot=_classer_type(libelle),
            ))
            acceptees += 1
            if acceptees % batch == 0:
                s.flush()
    H.enregistrer_import(s, domaine="epargne", fichier=os.path.basename(path),
                         date_snapshot=date_snapshot, date_arrete=date_arrete,
                         acceptees=acceptees, rejetees=0, message=f"purge {purges}")
    s.commit()
    s.close()
    return {"acceptees": acceptees, "purges": purges}


if __name__ == "__main__":
    import sys
    print(importer_epargne(sys.argv[1], dt.date.fromisoformat(sys.argv[2])))
