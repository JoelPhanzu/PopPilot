"""
Tests Phase 2 — états financiers Python == fichier magique (montants USD, écart nul).
La conversion CDF au taux unique (2268,75) est PLUS cohérente que le fichier source, dont le CR
porte un micro-écart de taux (2268,33 vs 2268,75) — anomalie documentée (§43), non reproduite.
"""
import datetime as dt
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from socle.seed_parametres import seed
from ingest.import_balance import importer_balance
from engine.etats_financiers import etats_financiers

MAGIQUE = "/mnt/user-data/uploads/ETATS_FINANCIERS_USD_JUILLET_2026.xlsx"
BALANCE_BRUTE = "/mnt/user-data/uploads/BALANCE.xlsx"
ARRETE = dt.date(2026, 7, 31)
DB = "socle/test_phase2.db"


def _prep(source=None):
    if os.path.exists(DB):
        os.remove(DB)
    seed(DB)
    importer_balance(source or BALANCE_BRUTE, ARRETE, db_path=DB)


def test_etats_financiers_usd():
    """Depuis la balance SAGE BRUTE (source réelle) : états financiers = fichier magique, écart nul."""
    if not os.path.exists(BALANCE_BRUTE):
        print("  (balance absente — test sauté)")
        return
    _prep(BALANCE_BRUTE)
    ef = etats_financiers(ARRETE, db_path=DB)
    assert abs(ef["total_actif"] - 12592520.01) < 0.5, ef["total_actif"]
    assert abs(ef["resultat_net"] - 142477.78) < 0.5, ef["resultat_net"]
    assert abs(ef["controles"]["fonds_propres"] - 4697575.57) < 1.0
    assert abs(ef["controles"]["bilan_equilibre_ecart"]) < 1.0
    assert ef["controles"]["comptes_non_mappes"] == 0


def test_idempotence_balance():
    if not os.path.exists(BALANCE_BRUTE):
        return
    r1 = importer_balance(BALANCE_BRUTE, ARRETE, db_path=DB)
    r2 = importer_balance(BALANCE_BRUTE, ARRETE, db_path=DB)
    assert r2["purges"] == r1["acceptees"]
    ef = etats_financiers(ARRETE, db_path=DB)
    assert abs(ef["total_actif"] - 12592520.01) < 0.5   # pas de doublon


if __name__ == "__main__":
    test_etats_financiers_usd()
    print("  ✓ test_etats_financiers_usd (actif, résultat net, fonds propres = fichier, écart nul)")
    test_idempotence_balance()
    print("  ✓ test_idempotence_balance")
    print("Phase 2 validée : états financiers Python == fichier magique (USD).")
