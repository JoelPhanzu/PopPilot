"""Tests FINA — génération depuis la balance CDF (sans conversion), cohérences inter-feuilles."""
import datetime as dt
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from socle.seed_parametres import seed
from socle.agences import seed_agences
from ingest.import_credit import importer_credit
from ingest.import_balance import importer_balance
from engine.fina import generer_fina

COMBINE = "/mnt/user-data/uploads/Juillet_2026_Encours_et_balance.xlsx"
BALANCE_CDF = "/mnt/user-data/uploads/ETATS_FINANCIERS_CDF_JUILLET_2026.xlsx"
ARRETE = dt.date(2026, 7, 31)
DB = "socle/test_fina.db"


def _prep():
    if not (os.path.exists(COMBINE) and os.path.exists(BALANCE_CDF)):
        return False
    if os.path.exists(DB):
        os.remove(DB)
    seed(DB); seed_agences(DB)
    importer_credit(COMBINE, ARRETE, feuille="Encours", db_path=DB)
    importer_balance(BALANCE_CDF, ARRETE, devise="CDF", db_path=DB)
    return True


def test_fina_montants_cdf():
    """F5 : encours CT/MT/retard en CDF = gabarit FINA, DEPUIS la balance CDF (sans conversion)."""
    if not _prep():
        print("  (fichiers absents — test sauté)")
        return
    r = generer_fina(ARRETE, db_path=DB)
    f5 = r["F5"]
    assert abs(f5["CT_total_cdf"] - 14983445550.77) < 5, f5["CT_total_cdf"]
    assert abs(f5["MT_total_cdf"] - 6856955065.13) < 5, f5["MT_total_cdf"]
    assert abs(f5["retard_total_cdf"] - 3059025409.49) < 5, f5["retard_total_cdf"]
    assert abs(f5["total_cdf"] - 24899426025.39) < 5, f5["total_cdf"]


def test_fina_coherences():
    """Cohérences inter-feuilles vertes, écart 0 (tout en CDF, §35)."""
    r = generer_fina(ARRETE, db_path=DB)
    assert r["controles"]["X2_F5_total_vs_bilan"]["ok"]
    assert r["controles"]["X2_F11_encours_vs_bilan"]["ok"]


def test_fina_groupe_lisanga():
    """Ventilation groupe LISANGA : total CT groupe = 3 172 238 623 CDF (gabarit)."""
    r = generer_fina(ARRETE, db_path=DB)
    total_groupe = r["F5"]["groupe_sain_cdf"] + r["F5"]["groupe_retard_cdf"]
    assert abs(total_groupe - 3172238623) < 5000, total_groupe


if __name__ == "__main__":
    if _prep():
        test_fina_montants_cdf()
        print("  ✓ test_fina_montants_cdf (CT/MT/retard = gabarit, depuis balance CDF)")
        test_fina_coherences()
        print("  ✓ test_fina_coherences (cohérences vertes, écart 0)")
        test_fina_groupe_lisanga()
        print("  ✓ test_fina_groupe_lisanga (3 172 238 623 CDF)")
        print("FINA validé depuis balance CDF, sans conversion.")
    else:
        print("  (fichiers absents)")
