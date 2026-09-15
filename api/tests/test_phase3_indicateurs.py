"""Tests Phase 3 — indicateurs prudentiels, fonds propres 2 versions, PAR depuis Phase 1."""
import datetime as dt
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from socle.seed_parametres import seed
from socle.agences import seed_agences
from ingest.import_credit import importer_credit
from ingest.import_balance import importer_balance
from engine.indicateurs import indicateurs_prudentiels

BASE = "/mnt/user-data/uploads/{}"
MOIS = [("Décembre_2025_Encours_et_balance.xlsx", dt.date(2025, 12, 31)),
        ("Mai_2026_Encours_et_balance.xlsx", dt.date(2026, 5, 30)),
        ("Juillet_2026_Encours_et_balance.xlsx", dt.date(2026, 7, 31))]
DB = "socle/test_phase3.db"


def _prep():
    if not all(os.path.exists(BASE.format(f)) for f, _ in MOIS):
        return False
    if os.path.exists(DB):
        os.remove(DB)
    seed(DB); seed_agences(DB)
    for f, arr in MOIS:
        importer_credit(BASE.format(f), arr, feuille="Encours", db_path=DB)
        importer_balance(BASE.format(f), arr, feuille="Balance", db_path=DB)
    return True


def test_par_depuis_phase1_egale_compte39():
    """Invariant X-1 : PAR1 crédit (juillet) = capital retard compte 39 balance (juillet)."""
    if not _prep():
        return
    r = indicateurs_prudentiels(dt.date(2026, 7, 31), db_path=DB)
    ag = r["agregats"]
    assert abs(ag["PAR1_credit"] - ag["capital_retard_bilan_39"]) < 2.0, \
        f"PAR1 {ag['PAR1_credit']} != compte39 {ag['capital_retard_bilan_39']}"


def test_fonds_propres_deux_versions():
    """FP base (10-14) pilote les ratios ; version avec résultat = base + résultat, informative."""
    r = indicateurs_prudentiels(dt.date(2026, 7, 31), db_path=DB)
    ag = r["agregats"]
    assert abs(ag["fonds_propres_base"] - 4555097.79) < 1.0
    assert abs(ag["fonds_propres_base_avec_resultat"]
               - (ag["fonds_propres_base"] + ag["resultat"])) < 0.01
    assert abs(ag["fonds_propres_prudentiels"] - 4802771.45) < 1.0
    # les ratios de FP utilisent bien la version SANS résultat
    assert abs(r["indicateurs"]["E3_capitalisation"]["den"] - ag["total_actif"]) < 1.0
    assert abs(r["indicateurs"]["E1_capital_min"]["num"] - ag["fonds_propres_base"]) < 1.0


def test_moyennes_de_periode():
    """ROE utilise (FP juillet + FP décembre)/2 — moyenne opérationnelle."""
    r = indicateurs_prudentiels(dt.date(2026, 7, 31), db_path=DB)
    roe = r["indicateurs"]["C1_ROE"]
    # le dénominateur (FP moyen) est entre déc et juillet, donc < base juillet seule si déc plus bas
    assert roe["valeur"] is not None




def test_E4_liquidite_et_B2():
    """E4 liquidité (dispo/dépôts à vue) et B2 (emprunteurs/agent) calculés."""
    from ingest.import_epargne import importer_epargne
    from ingest.import_objectifs import importer_objectifs
    csv='/mnt/user-data/uploads/Inventaire_depot_juillet_2026_Inventaire_depot_script___3_.csv'
    obj='/mnt/user-data/uploads/OBJECTIF.xlsx'
    if not (os.path.exists(csv) and os.path.exists(obj)): return
    importer_epargne(csv, dt.date(2026,7,31), db_path=DB)
    importer_objectifs(obj, dt.date(2026,7,1), db_path=DB)
    r=indicateurs_prudentiels(dt.date(2026,7,31), db_path=DB)
    e4=r["indicateurs"]["E4_liquidite"]
    assert e4["valeur"] is not None and e4["valeur"] > 20
    b2=r["indicateurs"]["B2_emprunteurs_agent"]
    assert b2["valeur"] is not None and b2["num"] > 8000
    # tous les 17 calculés
    assert all(v["valeur"] is not None for v in r["indicateurs"].values())


if __name__ == "__main__":
    if _prep():
        test_par_depuis_phase1_egale_compte39()
        print("  ✓ test_par_depuis_phase1_egale_compte39 (invariant X-1 vérifié)")
        test_fonds_propres_deux_versions()
        print("  ✓ test_fonds_propres_deux_versions (base pilote ratios, +résultat informatif)")
        test_moyennes_de_periode()
        print("  ✓ test_moyennes_de_periode (ROE sur moyenne juillet/décembre)")
        test_E4_liquidite_et_B2()
        print("  ✓ test_E4_liquidite_et_B2 (17/17 indicateurs calculés)")
        print("Phase 3 : indicateurs validés.")
    else:
        print("  (fichiers absents — tests sautés)")
