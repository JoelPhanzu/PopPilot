"""Tests Phase 3 — indicateurs prudentiels, fonds propres 2 versions, PAR depuis Phase 1."""
import datetime as dt
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import donnees_test as D   # localise les sources reelles + compte rendu honnete

from socle.seed_parametres import seed
from socle.schema import fermer_moteurs
from socle.agences import seed_agences
from ingest.import_credit import importer_credit
from ingest.import_balance import importer_balance
from engine.indicateurs import indicateurs_prudentiels

# Un mois = (extraction credit, balance USD, date d'arrete).
#
# Les fichiers combines « <Mois>_Encours_et_balance.xlsx » (feuille Encours + feuille
# Balance) n'existaient que dans un environnement de travail anterieur. La plateforme
# lit desormais les fichiers TELS QUE LE CBS ET LA COMPTA LES PRODUISENT : l'extraction
# credit d'un cote, les etats financiers de l'autre. Plus d'assemblage manuel prealable.
#
# Balance en USD (decision CDG) : les indicateurs prudentiels et les fonds propres sont
# libelles en USD, comme la Phase 2 deja validee (total actif 12 592 520,01 USD).
# Le CDF reste reserve au FINA, qui est un rapport en francs.
MOIS = [("Encours_credit_DECEMBRE_2025.xls",  "ETATS_FINANCIERS_USD_DEC_2025.xlsx",     dt.date(2025, 12, 31)),
        ("Enours_MAI_2026_.xls",              "ETATS_FINANCIERS_USD_MAI_2026.xlsx",     dt.date(2026, 5, 30)),
        ("Encours_credit_JUILLET_2026.xlsx",  "ETATS_FINANCIERS_USD_JUILLET_2026.xlsx", dt.date(2026, 7, 31))]
DB = "socle/test_phase3.db"


_charge = False


def _prep():
    """Charge les 3 mois UNE fois. Saute le test (sans le faire passer) si une source manque.

    Chaque test appelle _prep() : avant, seul le premier le faisait et les suivants
    dependaient de son effet de bord. Des qu'il etait saute, ils plantaient sur
    "no such table" au lieu d'etre sautes eux aussi.
    """
    global _charge
    manquants = [f for couple in MOIS for f in couple[:2] if D.fichier(f) is None]
    if manquants:
        raise D.TestSaute("sources absentes : " + ", ".join(manquants))
    if _charge:
        return True
    fermer_moteurs()
    if os.path.exists(DB):
        os.remove(DB)
    seed(DB); seed_agences(DB)
    for f_credit, f_balance, arr in MOIS:
        importer_credit(D.exiger(f_credit), arr, db_path=DB)
        importer_balance(D.exiger(f_balance), arr, feuille="Balance", db_path=DB)
    _charge = True
    return True


def test_par_depuis_phase1_egale_compte39():
    """Invariant X-1 : PAR1 crédit (juillet) = capital retard compte 39 balance (juillet)."""
    _prep()
    r = indicateurs_prudentiels(dt.date(2026, 7, 31), db_path=DB)
    ag = r["agregats"]
    assert abs(ag["PAR1_credit"] - ag["capital_retard_bilan_39"]) < 2.0, \
        f"PAR1 {ag['PAR1_credit']} != compte39 {ag['capital_retard_bilan_39']}"


def test_fonds_propres_deux_versions():
    """FP base (10-14) pilote les ratios ; version avec résultat = base + résultat, informative."""
    _prep()
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
    """ROE utilise VRAIMENT (FP juillet + FP décembre)/2, et pas les soldes de juillet seuls.

    L'ancien test se contentait de `valeur is not None` : il passait alors même que les
    moyennes échouaient (le 31/12/2025 n'a pas de taux de change saisi, et le bilan
    refusait de se calculer sans taux). Les ratios ROE/ROA/B1/C3 sortaient donc sur des
    soldes ponctuels, sous une étiquette « moyenne de période ». On vérifie le calcul.
    """
    _prep()
    r = indicateurs_prudentiels(dt.date(2026, 7, 31), db_path=DB)
    assert r["moyennes_de_periode"] is True, r["avertissements"]

    fp_juillet = r["agregats"]["fonds_propres_base"]
    fp_decembre = indicateurs_prudentiels(
        dt.date(2025, 12, 31), db_path=DB)["agregats"]["fonds_propres_base"]
    attendu = (fp_juillet + fp_decembre) / 2
    roe = r["indicateurs"]["C1_ROE"]
    assert abs(roe["den"] - attendu) < 1.0, (roe["den"], attendu)
    assert abs(roe["den"] - fp_juillet) > 1.0, "le dénominateur est le solde de juillet, pas une moyenne"




def test_E4_liquidite_et_B2():
    """E4 liquidité (dispo/dépôts à vue) et B2 (emprunteurs/agent) calculés."""
    _prep()
    from ingest.import_epargne import importer_epargne
    from ingest.import_objectifs import importer_objectifs
    inv = "Inventaire_depot_juillet_2026_Inventaire_depot_script___3_"
    csv = D.exiger_un_de(inv + ".csv", inv + ".xlsx")
    obj = D.exiger("OBJECTIF.xlsx")
    importer_epargne(csv, dt.date(2026,7,31), db_path=DB)
    importer_objectifs(obj, dt.date(2026,7,1), db_path=DB)
    r=indicateurs_prudentiels(dt.date(2026,7,31), db_path=DB)
    e4=r["indicateurs"]["E4_liquidite"]
    assert e4["valeur"] is not None and e4["valeur"] > 20
    b2=r["indicateurs"]["B2_emprunteurs_agent"]
    assert b2["valeur"] is not None and b2["num"] > 8000
    # le roster est versionné : B2 doit compter les agents d'UNE seule version, pas
    # l'empilement de tous les mois importés
    assert 20 <= b2["den"] <= 60, f"nb agents {b2['den']} (roster empilé ?)"

    # Deux indicateurs ne sont PAS calculables en l'état, et le disent :
    #   A2 (abandons) attend le moteur de radiation ; E6 attend la distinction > 1 an.
    # Les compter comme « calculés » revenait à afficher A2 = 0 %, donc conforme.
    non_calcules = {k for k, v in r["indicateurs"].items() if v["valeur"] is None}
    assert non_calcules == {"A2_abandon", "E6_couverture_emplois_MLT"}, non_calcules
    assert all(r["indicateurs"][k].get("motif") for k in non_calcules)
    calcules = [k for k, v in r["indicateurs"].items() if v["valeur"] is not None]
    assert len(calcules) == 16, calcules       # 15 du catalogue + A1bis (PAR1)


if __name__ == "__main__":
    D.sortir(D.lancer("Phase 3 - indicateurs prudentiels", [
        (test_par_depuis_phase1_egale_compte39, "PAR depuis Phase 1 = compte 39 (invariant X-1)"),
        (test_fonds_propres_deux_versions,      "fonds propres 2 versions (base pilote les ratios)"),
        (test_moyennes_de_periode,              "moyennes de periode (ROE juillet/decembre)"),
        (test_E4_liquidite_et_B2,               "E4 liquidite + B2 ; indicateurs non calculables declares"),
    ]))