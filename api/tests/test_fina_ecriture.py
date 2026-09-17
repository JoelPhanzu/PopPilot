"""Test génération FINA .xls complet — F0, F1, F2, F5, F11."""
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
from ingest.import_epargne import importer_epargne
from engine.fina_ecriture import valeurs_fina, ecrire_fina

# Extraction credit juillet, telle que produite par le CBS (feuille "Worksheet").
CREDIT = "Encours_credit_JUILLET_2026.xlsx"
# FINA = rapport en CDF -> balance CDF, sans conversion (CLAUDE.md, doctrine multidevise).
BALANCE_CDF = "ETATS_FINANCIERS_CDF_JUILLET_2026.xlsx"
INVENTAIRE = "Inventaire_depot_juillet_2026_Inventaire_depot_script___3_"
ARRETE = dt.date(2026, 7, 31)
DB = "socle/test_finaw.db"


def _prep():
    """Charge credit + balance CDF + epargne. Saute (sans faire passer) si une source manque."""
    D.exiger(CREDIT)
    D.exiger(BALANCE_CDF)
    D.exiger_un_de(INVENTAIRE + ".csv", INVENTAIRE + ".xlsx")
    fermer_moteurs()
    if os.path.exists(DB):
        os.remove(DB)
    seed(DB); seed_agences(DB)
    importer_credit(D.exiger(CREDIT), ARRETE, db_path=DB)
    importer_balance(D.exiger(BALANCE_CDF), ARRETE,
                     feuille="Balance", devise="CDF", db_path=DB)
    importer_epargne(D.exiger_un_de(INVENTAIRE + ".csv", INVENTAIRE + ".xlsx"),
                     ARRETE, db_path=DB)
    return True


def test_fina_complet():
    _prep()
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


def test_comptes_mixtes_jamais_negatifs():
    """Un compte mixte se répartit selon le signe : aucune ligne du bilan n'est négative.

    Défaut corrigé : le solde NET d'un compte mixte (40, 42-47, 53, 56) était écrit à
    l'actif ET au passif. F0a.05 sortait à −1 782 915 519 CDF. Une déclaration BCC ne
    porte pas d'actif négatif.
    """
    _prep()
    ag = valeurs_fina(ARRETE, db_path=DB)
    for case in ("F0a.05", "F0a.16", "F0a.18", "F0a.21", "F0a.22", "F0a.04",
                 "F0p.04", "F0p.12", "F0p.13", "F0p.14", "F0p.17", "F0p.18"):
        assert ag[case] >= 0, f"{case} negatif : {ag[case]:,.2f}"
    assert not ag["_F0_mixtes_non_affectes"], ag["_F0_mixtes_non_affectes"]


def test_f0_egale_le_bilan():
    """Les lignes F0 (case par case) redonnent le bilan (mapping par préfixe) : deux chemins."""
    _prep()
    ag = valeurs_fina(ARRETE, db_path=DB)
    assert ag["_F0_controle"] == "ok", {
        "ecart_actif": ag["_F0_ecart_actif"], "ecart_passif": ag["_F0_ecart_passif"],
        "actif_F0": ag["_F0_actif_total"], "actif_bilan": ag["_F0_bilan_actif"]}


def test_part_groupe_epargne_homogene():
    """La part groupe F6 se calcule sur une base homogène (USD), pas sur un mélange USD+CDF.

    En devise d'origine, la somme mêlait des USD et des CDF bruts : la part groupe
    tombait à 0,02 % au lieu de 1,82 %, soit un facteur 100 sur la ventilation F6.
    """
    _prep()
    ag = valeurs_fina(ARRETE, db_path=DB)
    assert ag["_F6_groupe_indisponible"] is None, ag["_F6_groupe_indisponible"]
    assert 0.01 < ag["_F6_part_groupe"] < 0.05, ag["_F6_part_groupe"]
    assert abs(ag["F6_33_client"] + ag["F6_33_groupe"] - ag["F6_33_total"]) < 1


def test_ecriture_du_gabarit_xls():
    """L'écriture RÉELLE du .xls (xlutils/xlwt), jamais exercée jusqu'ici.

    Les tests n'appelaient que valeurs_fina : ni les dépendances d'écriture ni le
    remplissage des feuilles n'étaient vérifiés. Sauté proprement si le gabarit BCC
    (MFII*.xls, non versionné) n'est pas dans le dossier de données.
    """
    import glob
    import tempfile
    gabarits = sorted(glob.glob(os.path.join(D.dossier_donnees(), "MFII*.xls")))
    if not gabarits:
        raise D.TestSaute(f"gabarit BCC MFII*.xls absent de {D.dossier_donnees()}")
    _prep()
    sortie = os.path.join(tempfile.gettempdir(), "FINA_test_ecriture.xls")
    r = ecrire_fina(ARRETE, gabarits[0], sortie, db_path=DB,
                    rh={"nb_employes": 126, "nb_agents_credit": 29},
                    ventilation_f10={"commerce": 0.81, "agricole": 0.0,
                                     "services": 0.15, "autres": 0.04})
    assert os.path.exists(sortie)
    import xlrd
    wb = xlrd.open_workbook(sortie)
    for feuille in ("F0", "F1", "F5", "F11"):
        assert feuille in wb.sheet_names(), feuille
    # les feuilles hors périmètre ne doivent pas avoir été touchées
    assert abs(r["F5_total"] - 24899426025) < 100
    os.remove(sortie)


def _gabarit_minimal(chemin):
    """Gabarit .xls de test portant les codes que `ecrire_fina` cherche.

    Il ne remplace pas le vrai MFII (les montants attendus viennent de celui-là), mais
    il permet de tester l'ÉCRITURE elle-même sans dépendre d'un fichier non versionné.
    """
    import xlwt
    wb = xlwt.Workbook()
    codes = {"F0": ["V1.F0a.09", "V1.F0p.25"], "F1": ["V1.F1.26"], "F2": ["V1.F2b.01"],
             "F5": ["V1.F5.15"], "F11": ["V1.F11.01", "V1.F11.22"],
             "F6": ["V1.F6.01", "V1.F6.08", "V1.F6.10"], "F7": ["V1.F7.04", "V1.F7.07"],
             "F10": ["V1.F10.02"], "F3": [], "F4a": [], "F8": [], "F9": [], "F12": []}
    for nom, lignes in codes.items():
        ws = wb.add_sheet(nom)
        for i, c in enumerate(lignes):
            ws.write(i, 0, c)
        if not lignes:
            ws.write(0, 0, "INTOUCHABLE")
    wb.save(chemin)
    return chemin


def test_case_indisponible_ne_perd_pas_le_rapport():
    """Une case sans donnée coûte UNE CASE, jamais le rapport entier.

    `valeurs_fina` met la ventilation groupe de F6 à None quand l'épargne du mois n'est
    pas chargée (ou le taux pas saisi) — c'est voulu. Mais le bloc d'écriture faisait
    `round(None, 2)` : TypeError, et le FINA ENTIER était perdu, F0/F1/F5/F11 compris,
    alors que ces feuilles-là étaient parfaitement calculées. Une déclaration BCC ne
    doit pas disparaître parce qu'une sous-ligne manque — mais elle doit se DIRE
    incomplète, sinon on livre un gabarit à trous sans le savoir.
    """
    import tempfile
    import xlrd
    from socle.schema import init_db, get_session, FaitBalance

    fermer_moteurs()
    db = "socle/test_fina_case_vide.db"
    if os.path.exists(db):
        os.remove(db)
    init_db(db)
    s = get_session(db)
    # Balance CDF seule : AUCUNE épargne, AUCUN taux saisi.
    for compte, solde in [("3200", 1e6), ("3100", 5e5), ("3900", 1e5),
                          ("3300", -8e5), ("3400", -2e5), ("3500", -1e5)]:
        s.add(FaitBalance(date_arrete=ARRETE, date_snapshot=ARRETE,
                          numero_compte=compte, solde_net=solde, devise="CDF"))
    s.commit(); s.close()

    tmp = tempfile.gettempdir()
    gabarit = _gabarit_minimal(os.path.join(tmp, "FINA_gabarit_minimal.xls"))
    sortie = os.path.join(tmp, "FINA_case_vide.xls")
    r = ecrire_fina(ARRETE, gabarit, sortie, db_path=db)

    assert os.path.exists(sortie), "le rapport n'a pas ete produit"
    assert r["complet"] is False, "un rapport a trous doit se declarer incomplet"
    assert any("F6.01" in c for c in r["cases_vides"]), r["cases_vides"]

    wb = xlrd.open_workbook(sortie)
    f6 = wb.sheet_by_name("F6")
    assert f6.cell_value(0, 5) == 800000.0, "le TOTAL F6 (balance) devait etre ecrit"
    assert f6.cell_value(0, 2) == "", "la ventilation groupe ne devait PAS etre ecrite"
    # le reste du rapport est bien la : c'est tout l'enjeu
    assert wb.sheet_by_name("F5").cell_value(0, 5) == 1000000.0
    assert wb.sheet_by_name("F9").cell_value(0, 0) == "INTOUCHABLE"

    fermer_moteurs()
    os.remove(sortie)
    if os.path.exists(db):
        os.remove(db)


if __name__ == "__main__":
    D.sortir(D.lancer("FINA - ecriture du gabarit .xls", [
        (test_case_indisponible_ne_perd_pas_le_rapport,
         "une case sans donnee ne fait pas perdre le rapport"),
        (test_fina_complet, "F0, F1, F2, F5, F11 ecrits = gabarit BCC"),
        (test_comptes_mixtes_jamais_negatifs, "comptes mixtes repartis par signe (aucun negatif)"),
        (test_f0_egale_le_bilan, "somme des lignes F0 = bilan de la balance CDF"),
        (test_part_groupe_epargne_homogene, "part groupe F6 calculee en base homogene"),
        (test_ecriture_du_gabarit_xls, "ecriture reelle du .xls (xlutils/xlwt)"),
    ]))