"""
Tests Phase 2 — états financiers Python == fichier magique (montants USD, écart nul).
La conversion CDF au taux unique (2268,75) est PLUS cohérente que le fichier source, dont le CR
porte un micro-écart de taux (2268,33 vs 2268,75) — anomalie documentée (§43), non reproduite.
"""
import datetime as dt
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import donnees_test as D   # localise les sources reelles + compte rendu honnete

from socle.schema import fermer_moteurs
from socle.seed_parametres import seed
from ingest.import_balance import importer_balance
from engine.etats_financiers import etats_financiers

MAGIQUE = D.fichier("ETATS_FINANCIERS_USD_JUILLET_2026.xlsx") or "(source absente : ETATS_FINANCIERS_USD_JUILLET_2026.xlsx)"
BALANCE_BRUTE = D.fichier("BALANCE.xlsx") or "(source absente : BALANCE.xlsx)"
ARRETE = dt.date(2026, 7, 31)
DB = "socle/test_phase2.db"


def _prep(source=None):
    fermer_moteurs()
    if os.path.exists(DB):
        os.remove(DB)
    seed(DB)
    importer_balance(source or BALANCE_BRUTE, ARRETE, db_path=DB)


def test_etats_financiers_usd():
    """Depuis la balance SAGE BRUTE (source réelle) : états financiers = fichier magique, écart nul."""
    D.exiger("BALANCE.xlsx")
    _prep(BALANCE_BRUTE)
    ef = etats_financiers(ARRETE, db_path=DB)
    assert abs(ef["total_actif"] - 12592520.01) < 0.5, ef["total_actif"]
    assert abs(ef["resultat_net"] - 142477.78) < 0.5, ef["resultat_net"]
    assert abs(ef["controles"]["fonds_propres"] - 4697575.57) < 1.0
    assert abs(ef["controles"]["bilan_equilibre_ecart"]) < 1.0
    assert ef["controles"]["comptes_non_mappes"] == 0


def test_idempotence_balance():
    D.exiger("BALANCE.xlsx")
    r1 = importer_balance(BALANCE_BRUTE, ARRETE, db_path=DB)
    r2 = importer_balance(BALANCE_BRUTE, ARRETE, db_path=DB)
    assert r2["purges"] == r1["acceptees"]
    ef = etats_financiers(ARRETE, db_path=DB)
    assert abs(ef["total_actif"] - 12592520.01) < 0.5   # pas de doublon


BALANCE_CDF = D.fichier("ETATS_FINANCIERS_CDF_JUILLET_2026.xlsx") or \
    "(source absente : ETATS_FINANCIERS_CDF_JUILLET_2026.xlsx)"


def test_balances_usd_et_cdf_coexistent():
    """Les DEUX balances d'un même arrêté cohabitent : la CDF (FINA) n'écrase pas l'USD (bilan).

    Le défaut corrigé : la purge d'import ignorait la devise et la clé d'unicité aussi.
    Importer la balance CDF supprimait donc la balance USD, et `etats_financiers`
    relisait les montants CDF comme des USD — total actif à 29 milliards « USD »,
    sans la moindre erreur. Ce test échoue si la devise ressort de la clé.
    """
    D.exiger("BALANCE.xlsx"); D.exiger("ETATS_FINANCIERS_CDF_JUILLET_2026.xlsx")
    _prep(BALANCE_BRUTE)                                   # balance USD
    importer_balance(BALANCE_CDF, ARRETE, feuille="Balance", devise="CDF", db_path=DB)

    ef = etats_financiers(ARRETE, db_path=DB)              # USD par défaut
    assert abs(ef["total_actif"] - 12592520.01) < 0.5, \
        f"la balance CDF a pollué le bilan USD : total actif {ef['total_actif']}"

    from engine.fina import _soldes_cdf
    from socle.schema import get_session
    s = get_session(DB)
    soldes_cdf = _soldes_cdf(s, ARRETE)
    s.close()
    assert soldes_cdf, "la balance CDF doit rester lisible pour le FINA"
    # l'encours crédit CDF (31+32+39) est sans commune mesure avec l'USD : preuve
    # que chaque moteur lit bien SA devise.
    enc_cdf = sum(v for c, v in soldes_cdf.items() if c[:2] in ("31", "32", "39"))
    assert enc_cdf > 1e9, enc_cdf


if __name__ == "__main__":
    D.sortir(D.lancer("Phase 2 - comptabilite", [
        (test_etats_financiers_usd, "etats financiers USD = fichier magique (ecart nul)"),
        (test_idempotence_balance,  "import balance idempotent"),
        (test_balances_usd_et_cdf_coexistent,
         "balances USD et CDF du meme arrete coexistent (pas d'ecrasement)"),
    ]))