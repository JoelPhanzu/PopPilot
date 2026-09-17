"""Tests FINA — génération depuis la balance CDF (sans conversion), cohérences inter-feuilles."""
import datetime as dt
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import donnees_test as D   # localise les sources reelles + compte rendu honnete

from socle.schema import fermer_moteurs
from socle.seed_parametres import seed
from socle.agences import seed_agences
from ingest.import_credit import importer_credit
from ingest.import_balance import importer_balance
from engine.fina import generer_fina

# Extraction credit juillet, telle que produite par le CBS (feuille "Worksheet").
CREDIT = "Encours_credit_JUILLET_2026.xlsx"
# FINA = rapport en CDF -> balance CDF, sans conversion (CLAUDE.md, doctrine multidevise).
BALANCE_CDF = "ETATS_FINANCIERS_CDF_JUILLET_2026.xlsx"
ARRETE = dt.date(2026, 7, 31)
DB = "socle/test_fina.db"


_charge = False


def _prep():
    """Charge credit + balance CDF UNE fois. Saute (sans faire passer) si une source manque."""
    global _charge
    D.exiger(CREDIT)
    D.exiger(BALANCE_CDF)
    if _charge:
        return True
    fermer_moteurs()
    if os.path.exists(DB):
        os.remove(DB)
    seed(DB); seed_agences(DB)
    importer_credit(D.exiger(CREDIT), ARRETE, db_path=DB)
    importer_balance(D.exiger(BALANCE_CDF), ARRETE,
                     feuille="Balance", devise="CDF", db_path=DB)
    _charge = True
    return True


def test_fina_montants_cdf():
    """F5 : encours CT/MT/retard en CDF = gabarit FINA, DEPUIS la balance CDF (sans conversion)."""
    _prep()
    r = generer_fina(ARRETE, db_path=DB)
    f5 = r["F5"]
    assert abs(f5["CT_total_cdf"] - 14983445550.77) < 5, f5["CT_total_cdf"]
    assert abs(f5["MT_total_cdf"] - 6856955065.13) < 5, f5["MT_total_cdf"]
    assert abs(f5["retard_total_cdf"] - 3059025409.49) < 5, f5["retard_total_cdf"]
    assert abs(f5["total_cdf"] - 24899426025.39) < 5, f5["total_cdf"]


def test_fina_coherences():
    """Cohérences inter-feuilles : deux sources INDÉPENDANTES doivent concorder (§35).

    Les anciens contrôles comparaient une variable à elle-même et ne pouvaient donc
    jamais échouer. Les nouveaux confrontent l'extraction crédit (USD) à la balance
    CDF, et les tranches d'âge du crédit au compte 39 de la balance.
    """
    _prep()
    r = generer_fina(ARRETE, db_path=DB)
    x1 = r["controles"]["X1_credit_vs_bilan"]
    assert x1["ok"], x1
    # le taux implicite (bilan CDF ÷ encours crédit USD) = le taux officiel saisi
    assert abs(x1["taux_implicite"] - x1["taux_officiel"]) < 0.01, x1
    assert r["controles"]["X2_F11_tranches_vs_compte_39"]["ok"], \
        r["controles"]["X2_F11_tranches_vs_compte_39"]
    assert r["controles"]["groupe_CT_coherent"]["ok"]


def test_fina_coherences_detectent_un_ecart():
    """Un contrôle qui ne peut pas échouer ne contrôle rien : on vérifie qu'il détecte.

    On fausse le taux officiel (comme le ferait un taux du mauvais mois) : X1 doit
    virer au rouge. Sans ce test, rien ne prouve que les cohérences sont autre chose
    qu'une décoration.
    """
    _prep()
    from ingest.taux_change import saisir_taux
    from engine.etats_financiers import taux_change  # noqa: F401 (documentation)
    saisir_taux(ARRETE, 2000.0, db_path=DB)          # taux manifestement faux
    try:
        r = generer_fina(ARRETE, db_path=DB)
        assert r["controles"]["X1_credit_vs_bilan"]["ok"] is False, \
            "X1 doit signaler un taux incohérent"
    finally:
        _prep()                                       # remettre la base d'aplomb


def test_fina_groupe_lisanga():
    """Ventilation groupe LISANGA : total CT groupe = 3 172 238 623 CDF (gabarit)."""
    _prep()
    r = generer_fina(ARRETE, db_path=DB)
    total_groupe = r["F5"]["groupe_sain_cdf"] + r["F5"]["groupe_retard_cdf"]
    assert abs(total_groupe - 3172238623) < 5000, total_groupe


if __name__ == "__main__":
    D.sortir(D.lancer("FINA - calcul", [
        (test_fina_montants_cdf,   "F5 CT/MT/retard = gabarit (depuis balance CDF)"),
        (test_fina_coherences,     "coherences inter-feuilles (sources independantes)"),
        (test_fina_coherences_detectent_un_ecart,
         "les coherences detectent bien un ecart (taux fausse)"),
        (test_fina_groupe_lisanga, "groupe LISANGA 3 172 238 623 CDF"),
    ]))