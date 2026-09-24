"""
Tests du tableau de bord crédit complet (engine/tableau_de_bord_credit.py).

Références : Dashboard DailyToolReporting de MAI 2026 (M-1 = avril), déjà validées moteur par
moteur dans test_phase1_par — ce tableau de bord doit les redonner AU CENTIME, puisqu'il ne fait
qu'assembler les mêmes moteurs sur un seul chargement :
  décaissements 1-31 mai 517 / 1 070 672 ; coût du risque 1 119,37 ; 120 entrées en PAR
  (116 482,40) ; migrations 5 tranches ; croissance −0,8904 % ; provisions 938 244,42 ;
  encours/PAR par agence (Dashboard).
Plus : Σ lignes = MICROPOP à chaque niveau ; P15 ; période de flux libre ; roster du mois.

Lancer :  python tests/test_tableau_de_bord_credit.py
"""
import datetime as dt
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import donnees_test as D   # noqa: E402

DB = "socle/test_tdb_credit.db"
MAI, AVRIL = dt.date(2026, 5, 30), dt.date(2026, 4, 30)
REF_AGENCES = {
    "AGENCE DE VICTOIRE": (2531178.47, 274877.29, 260281.47, 238210.18),
    "AGENCE OZONE": (1767802.20, 319713.96, 261424.23, 221564.02),
    "AGENCE DE GOMA": (1453955.88, 39926.86, 39402.33, 39402.33),
    "AGENCE DE LUBUMBASHI": (2027575.81, 240365.80, 230509.03, 208636.48),
    "AGENCE DE MASINA": (2027663.12, 222202.56, 181675.27, 158532.93),
    "AGENCE DE GOMBE": (1006155.18, 91360.75, 78825.72, 69563.83),
}
MIGR = {"31-60": 40814.15, "61-90": 69246.52, "91-180": 73868.45, "181-360": 55535.31,
        "361+": 66584.24}
_pret = []


def _tdb(**kw):
    if not _pret:
        import socle.schema as S
        os.environ.pop("DATABASE_URL", None)
        mai, avril = D.exiger("Enours_MAI_2026_.xls"), D.exiger("Encours_crédit_AVRIL_2026.xlsx")
        S.fermer_moteurs()
        if os.path.exists(DB):
            os.remove(DB)
        from socle.seed_parametres import seed
        from ingest.import_credit import importer_credit
        seed(DB)
        importer_credit(avril, AVRIL, date_snapshot=dt.date(2026, 5, 4), db_path=DB)
        importer_credit(mai, MAI, date_snapshot=dt.date(2026, 6, 1), db_path=DB)
        from socle.agences import seed_agences
        seed_agences(DB)                         # Goma FERMÉE, comme en production
        _pret.append(True)
    from engine.tableau_de_bord_credit import tableau_de_bord_credit
    kw.setdefault("debut", dt.date(2026, 5, 1))
    kw.setdefault("fin", dt.date(2026, 5, 31))
    return tableau_de_bord_credit(MAI, db_path=DB, **kw)


def test_micropop_egale_dashboard_mai():
    r = _tdb()
    g = r["lignes"][0]
    assert r["precedent"] == "2026-04-30"
    assert g["designation"] == "MICROPOP" and abs(g["encours"] - 10814330.66) < 0.01
    assert g["decaisse_nombre"] == 517 and abs(g["decaisse_volume"] - 1070672.00) < 0.5
    assert abs(g["cout_du_risque"] - 1119.37) < 0.02
    assert g["entree_par_nb"] == 120 and abs(g["entree_par_montant"] - 116482.40) < 0.02
    for tr, v in MIGR.items():
        assert abs(g["migration_vers"][tr] - v) < 0.05, tr
    assert abs(g["croissance"] - (-0.008904)) < 0.0001 and abs(g["encours_m1"] - 10911491.75) < 0.01
    assert abs(g["provisions"] - 938244.42) < 0.01
    assert abs(g["par30"] - 1052118.05) < 0.01


def test_agences_egalent_dashboard_et_somme():
    r = _tdb()
    g, agences = r["lignes"][0], {l["designation"]: l for l in r["lignes"][1:]}
    for nom, (enc, p1, p30, p90) in REF_AGENCES.items():
        l = agences[nom]
        for cle, v in (("encours", enc), ("par1", p1), ("par30", p30), ("par90", p90)):
            assert abs(l[cle] - v) < 0.01, (nom, cle, l[cle], v)
    for cle in ("encours", "decaisse_nombre", "decaisse_volume", "cout_du_risque",
                "entree_par_montant", "provisions", "encours_m1", "nb_credits", "p15"):
        assert abs(sum(l[cle] for l in agences.values()) - g[cle]) < 0.05, cle


def test_periode_de_flux_libre_et_p15():
    q1 = _tdb(fin=dt.date(2026, 5, 15))["lignes"][0]
    q2 = _tdb(debut=dt.date(2026, 5, 16))["lignes"][0]
    tout = _tdb()
    assert (q1["decaisse_nombre"], q2["decaisse_nombre"]) == (134, 383)       # Dashboard
    assert q1["decaisse_nombre"] + q2["decaisse_nombre"] == tout["lignes"][0]["decaisse_nombre"]
    assert tout["lignes"][0]["p15"] == 134                                   # P15 = 1er→15
    assert abs(q1["encours"] - tout["lignes"][0]["encours"]) < 0.01          # le stock ne bouge pas
    serie = tout["decaissements_jour"]
    assert len(serie) == 31 and serie[-1]["cumul_nombre"] == 517


def test_niveaux_roster_et_filtres():
    r = _tdb(niveau="agent")
    assert r["message"] and len(r["lignes"]) == 1                            # pas de roster → pas de ligne
    from ingest.import_objectifs import importer_objectifs
    importer_objectifs(D.exiger("OBJECTIF.xlsx"), dt.date(2026, 5, 1), db_path=DB)
    for niveau in ("agence", "superviseur", "agent"):
        r = _tdb(niveau=niveau)
        g, reste = r["lignes"][0], r["lignes"][1:]
        assert abs(sum(l["encours"] for l in reste) - g["encours"]) < 0.05, niveau
        assert abs(sum(l["cout_du_risque"] for l in reste) - g["cout_du_risque"]) < 0.05, niveau
    agents = _tdb(niveau="agent")["lignes"]
    assert any(l["statut"] == "orphelin" for l in agents) and any(l["statut"] == "gele" for l in agents)
    g = _tdb()["lignes"][0]
    assert g["nb_agents"] == 39 and g["p15_objectif"] == int(g["objectif_nombre"] / 2 + 0.5)
    assert abs(g["productivite"] - g["decaisse_nombre"] / 39) < 1e-9
    f = _tdb(filtres={"sexe": "F"})
    assert f["objectifs_applicables"] is False and f["lignes"][0]["objectif_nombre"] is None
    h = _tdb(filtres={"sexe": "H"})
    assert f["lignes"][0]["decaisse_nombre"] + h["lignes"][0]["decaisse_nombre"] == 517


if __name__ == "__main__":
    code = D.lancer("Tableau de bord credit complet", [
        (test_micropop_egale_dashboard_mai, "MICROPOP mai = Dashboard (décaissements, CR, migrations, croissance, provisions)"),
        (test_agences_egalent_dashboard_et_somme, "Agences = Dashboard ; Σ agences = MICROPOP"),
        (test_periode_de_flux_libre_et_p15, "Flux 1-15 / 16-31 mai = 134 / 383 ; P15 ; stock inchangé"),
        (test_niveaux_roster_et_filtres, "Niveaux agent/superviseur (roster), objectifs, productivité, filtres"),
    ])
    from socle.schema import fermer_moteurs
    fermer_moteurs()
    D.sortir(code)
