"""Test génération FINA .xls complet — F0, F1, F2, F5, F11."""
import datetime as dt
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from socle.seed_parametres import seed
from socle.agences import seed_agences
from ingest.import_credit import importer_credit
from ingest.import_balance import importer_balance
from ingest.import_epargne import importer_epargne
from engine.fina_ecriture import valeurs_fina

COMBINE = "/mnt/user-data/uploads/Juillet_2026_Encours_et_balance.xlsx"
BALANCE_CDF = "/mnt/user-data/uploads/ETATS_FINANCIERS_CDF_JUILLET_2026.xlsx"
CSV = "/mnt/user-data/uploads/Inventaire_depot_juillet_2026_Inventaire_depot_script___3_.csv"
ARRETE = dt.date(2026, 7, 31)
DB = "socle/test_finaw.db"


def _prep():
    if not all(os.path.exists(f) for f in (COMBINE, BALANCE_CDF, CSV)):
        return False
    if os.path.exists(DB):
        os.remove(DB)
    seed(DB); seed_agences(DB)
    importer_credit(COMBINE, ARRETE, feuille="Encours", db_path=DB)
    importer_balance(BALANCE_CDF, ARRETE, devise="CDF", db_path=DB)
    importer_epargne(CSV, ARRETE, db_path=DB)
    return True


def test_fina_complet():
    if not _prep():
        print("  (fichiers absents — test sauté)")
        return
    ag = valeurs_fina(ARRETE, db_path=DB, rh={"nb_employes": 126, "nb_agents_credit": 29})
    # F0/F1
    assert abs(ag["F0a.09"] - 14983445551) < 100
    assert abs(ag["F1.26"] - 366203898) < 100
    # F5
    assert abs(ag["F5_total"] - 24899426025) < 100
    assert abs(ag["F5_CT_groupe"] + ag["F5_retard_groupe"] - 3172238623) < 5000
    # F11
    assert abs(ag["F11_total_encours"] - 24899426025) < 100
    # F2 portée
    assert ag["F2b.01"] > 8000        # emprunteurs
    assert ag["F2b.03"] > 67000       # épargnants
    assert ag["F2b.05"] == 126        # employés (RH)
    assert ag["F2b.07"] == 29         # agents (RH)


if __name__ == "__main__":
    if _prep():
        test_fina_complet()
        print("  ✓ test_fina_complet (F0, F1, F2, F5, F11 = gabarit)")
        print("FINA complet validé.")
    else:
        print("  (fichiers absents)")
