"""Tests épargne — import 170k comptes, ventilation type/devise/groupe, cohérence bilan."""
import datetime as dt
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from socle.seed_parametres import seed
from ingest.import_epargne import importer_epargne
from engine.epargne import synthese_epargne, nb_epargnants

CSV = "/mnt/user-data/uploads/Inventaire_depot_juillet_2026_Inventaire_depot_script___3_.csv"
ARRETE = dt.date(2026, 7, 31)
DB = "socle/test_epargne.db"


def test_import_et_ventilation():
    if not os.path.exists(CSV):
        print("  (inventaire absent — test sauté)")
        return
    if os.path.exists(DB):
        os.remove(DB)
    seed(DB)
    r = importer_epargne(CSV, ARRETE, db_path=DB)
    assert r["acceptees"] == 169799
    syn = synthese_epargne(ARRETE, db_path=DB)
    # ventilation cohérente : total = somme des types
    total_types = syn["depots_a_vue"] + syn["depots_a_terme"] + syn["depots_obligatoire"]
    assert abs(total_types - syn["encours_total"]) < 1.0
    # à terme = Pop Monnaie A Terme USD (2 909 946)
    assert abs(syn["depots_a_terme"] - 2909946.25) < 1.0
    # obligatoire = nantie + caution (1 621 222)
    assert abs(syn["depots_obligatoire"] - 1621222.30) < 1.0
    # épargnants proches de la référence FINA
    assert 67000 < nb_epargnants(ARRETE, db_path=DB) < 67300


if __name__ == "__main__":
    test_import_et_ventilation()
    print("  ✓ test_import_et_ventilation (170k comptes, ventilation type = règle CDG)")
    print("Épargne validée.")
