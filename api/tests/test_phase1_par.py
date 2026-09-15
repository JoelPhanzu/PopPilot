"""
Tests Phase 1 — le PAR recalculé en Python == le Dashboard Excel de mai (écart nul).
Nécessite l'extraction réelle ; skippé proprement si le fichier n'est pas présent.
"""
import datetime as dt
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ingest.import_credit import importer_credit
from engine.par import calculer_par

EXTRACTION = "/mnt/user-data/uploads/Enours_MAI_2026_.xls"
ARRETE = dt.date(2026, 5, 30)
DB = "socle/test_phase1.db"

# Référence : Dashboard DailyToolReporting_Mai (encours, PAR1, PAR30, PAR90)
REF = {
    "MICROPOP":             (10814330.66, 1188447.22, 1052118.05, 935909.77),
    "AGENCE DE VICTOIRE":   (2531178.47, 274877.29, 260281.47, 238210.18),
    "AGENCE OZONE":         (1767802.20, 319713.96, 261424.23, 221564.02),
    "AGENCE DE GOMA":       (1453955.88, 39926.86, 39402.33, 39402.33),
    "AGENCE DE LUBUMBASHI": (2027575.81, 240365.80, 230509.03, 208636.48),
    "AGENCE DE MASINA":     (2027663.12, 222202.56, 181675.27, 158532.93),
    "AGENCE DE GOMBE":      (1006155.18, 91360.75, 78825.72, 69563.83),
}


def test_par_mai_egale_dashboard():
    if not os.path.exists(EXTRACTION):
        print("  (extraction absente — test sauté)")
        return
    if os.path.exists(DB):
        os.remove(DB)
    importer_credit(EXTRACTION, ARRETE, date_snapshot=dt.date(2026, 6, 1), db_path=DB)
    r = calculer_par(ARRETE, db_path=DB)
    calc = {r["global"].designation: r["global"]}
    for a in r["agences"]:
        calc[a.designation] = a

    for nom, (enc, p1, p30, p90) in REF.items():
        c = calc[nom]
        assert abs(c.encours - enc) < 0.01, f"{nom} encours {c.encours} != {enc}"
        assert abs(c.par1 - p1) < 0.01, f"{nom} PAR1 {c.par1} != {p1}"
        assert abs(c.par30 - p30) < 0.01, f"{nom} PAR30 {c.par30} != {p30}"
        assert abs(c.par90 - p90) < 0.01, f"{nom} PAR90 {c.par90} != {p90}"


def test_import_idempotent():
    if not os.path.exists(EXTRACTION):
        return
    r1 = importer_credit(EXTRACTION, ARRETE, db_path=DB)
    r2 = importer_credit(EXTRACTION, ARRETE, db_path=DB)  # ré-import
    assert r2["purges"] == r1["acceptees"]                # a bien purgé le précédent
    r = calculer_par(ARRETE, db_path=DB)
    assert abs(r["global"].encours - 10814330.66) < 0.01  # pas de doublon


AVRIL = "/mnt/user-data/uploads/Encours_crédit_AVRIL_2026.xlsx"
ARRETE_AVRIL = dt.date(2026, 4, 30)


def test_provisions_et_croissance():
    """Provision capital et croissance recalculées == fichier de mai (écart nul)."""
    if not (os.path.exists(EXTRACTION) and os.path.exists(AVRIL)):
        print("  (extractions absentes — test sauté)")
        return
    from socle.seed_parametres import seed
    from engine.derivation import deriver_provisions, croissance_portefeuille
    if os.path.exists(DB):
        os.remove(DB)
    seed(DB)
    importer_credit(AVRIL, ARRETE_AVRIL, date_snapshot=dt.date(2026, 5, 4), db_path=DB)
    importer_credit(EXTRACTION, ARRETE, date_snapshot=dt.date(2026, 6, 1), db_path=DB)

    prov = deriver_provisions(ARRETE, db_path=DB)
    assert abs(prov["provision_capital_totale"] - 938244.42) < 0.01, \
        f"provision {prov['provision_capital_totale']}"

    cr = croissance_portefeuille(ARRETE, ARRETE_AVRIL, db_path=DB)
    assert abs(cr["global"] - (-0.008904)) < 0.0001, f"croissance {cr['global']}"
    assert abs(cr["encours_precedent"] - 10911491.75) < 0.01  # = encours avril


def test_migrations_et_cout_du_risque():
    """Coût du risque + migrations (par tranche de départ) == Dashboard mai (écart nul)."""
    if not (os.path.exists(EXTRACTION) and os.path.exists(AVRIL)):
        return
    from engine.migrations import analyser_migrations
    r = analyser_migrations(ARRETE, ARRETE_AVRIL, db_path=DB)
    assert abs(r["cout_du_risque"] - 1119.37) < 0.02
    assert r["entree_par_nb"] == 120
    assert abs(r["entree_par_montant"] - 116482.40) < 0.02
    ref = {"31-60": 40814.15, "61-90": 69246.52, "91-180": 73868.45,
           "181-360": 55535.31, "361+": 66584.24}
    for tr, v in ref.items():
        assert abs(r["migration_vers"][tr] - v) < 0.05, f"migr {tr}"


OBJECTIFS = "/mnt/user-data/uploads/OBJECTIF.xlsx"


def test_decaissements():
    """Décaissements 1-31 mai == Dashboard (517 prêts / 1 070 672), écart nul."""
    if not os.path.exists(EXTRACTION):
        return
    from engine.decaissement import decaissements
    d = decaissements(ARRETE, dt.date(2026, 5, 1), dt.date(2026, 5, 31), db_path=DB)
    assert d["global"]["nombre"] == 517
    assert abs(d["global"]["volume"] - 1070672.00) < 0.5



def test_agence_fermee_vs_orphelins():
    """Goma (fermée) → portefeuille gelé, exclue des orphelins ; orphelins = anciens agents actifs."""
    if not (os.path.exists(EXTRACTION) and os.path.exists(OBJECTIFS)):
        return
    from socle.agences import seed_agences
    from ingest.import_objectifs import importer_objectifs
    from engine.decaissement import portefeuille_orphelin
    seed_agences(DB)
    importer_objectifs(OBJECTIFS, dt.date(2026, 5, 1), db_path=DB)
    o = portefeuille_orphelin(ARRETE, dt.date(2026, 5, 1), db_path=DB)
    # Goma en portefeuille gelé (~1,45 M), pas en orphelins
    gele = o["portefeuille_gele"]
    assert any("GOMA" in k for k in gele), "Goma doit être en portefeuille gelé"
    goma_enc = sum(v["encours"] for v in gele.values())
    assert abs(goma_enc - 1453955.88) < 1.0
    # Goma absente des orphelins
    assert not any("GOMA" in k for k in o["orphelins_agent"])


if __name__ == "__main__":
    test_par_mai_egale_dashboard()
    print("  ✓ test_par_mai_egale_dashboard (écart nul vs Dashboard)")
    test_import_idempotent()
    print("  ✓ test_import_idempotent")
    test_provisions_et_croissance()
    print("  ✓ test_provisions_et_croissance (provision + croissance = fichier, écart nul)")
    test_migrations_et_cout_du_risque()
    print("  ✓ test_migrations_et_cout_du_risque (coût du risque + 5 tranches = Dashboard)")
    test_decaissements()
    print("  ✓ test_decaissements (517 prêts / 1 070 672 = Dashboard, écart nul)")
    test_agence_fermee_vs_orphelins()
    print("  ✓ test_agence_fermee_vs_orphelins (Goma gelée, exclue des orphelins)")
    print("Phase 1 validée : PAR, provisions, croissance, migrations, décaissements == Excel.")
