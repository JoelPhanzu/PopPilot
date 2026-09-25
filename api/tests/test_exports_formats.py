"""
Tests : import du compte de résultat par agence dans TOUS les formats (xlsx, xls, csv, pdf),
lecture pilotée par les en-têtes, et exports CSV / Excel / PDF de n'importe quel tableau.

Garde-fous :
  - un même compte de résultat donne les MÊMES lignes quel que soit le format ;
  - le nombre d'agences varie (4 en janvier 2025) : la colonne MICROPOP n'est jamais lue
    comme une agence, ce qui suit MICROPOP (mois précédent recopié) est ignoré ;
  - colonne d'agence inconnue → refus ; MICROPOP vide alors que les agences ne le sont pas
    → refus (le contrôle n'est plus sauté en silence) ;
  - exports : un PDF est un PDF, l'Excel a une feuille par section, le CSV est « à la
    française » ; format inconnu → 422, export démesuré → 413.
"""
from __future__ import annotations

import csv
import datetime as dt
import io
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.pop("DATABASE_URL", None)

import donnees_test as D   # noqa: E402

NOMS_CR = ("COMPTE_RESULTAT_JUILLET_2026_isolé.xlsx",
           "COMPTE_RESULTAT_JUILLET_2026_isolé.xlsx",
           "COMPTE_RESULTAT_JUILLET_2026_isol├®.xlsx")
JUILLET = dt.date(2026, 7, 31)


def _lignes(path):
    from engine.import_compte_resultat_agence import importer_compte_resultat
    r = importer_compte_resultat(path, JUILLET)
    assert r["nb_alertes"] == 0, r["controles_incoherents"][:3]
    return {(l["poste"], l["agence"]): round(l["montant"], 2) for l in r["lignes"]}


def _fr(v):
    if isinstance(v, (int, float)):
        t = f"{abs(v):,.2f}".replace(",", " ").replace(".", ",")
        return f"({t})" if v < 0 else t
    return "" if v is None else str(v)


def test_compte_resultat_tous_formats():
    import openpyxl
    import xlwt
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
    source = D.exiger_un_de(*NOMS_CR)
    ref = _lignes(source)
    assert len(ref) == 174 and abs(sum(v for (p, _), v in ref.items()
                                       if p == "RESULTAT COMPTABLE") - 24798.80) < 0.02
    rows = [list(r[:9]) for r in openpyxl.load_workbook(source, data_only=True)["Feuil2"]
            .iter_rows(values_only=True)]
    dossier = tempfile.mkdtemp()
    try:
        wb = xlwt.Workbook()
        sh = wb.add_sheet("Feuil2")
        for i, r in enumerate(rows):
            for j, v in enumerate(r):
                if v is not None:
                    sh.write(i, j, v)
        wb.save(os.path.join(dossier, "cr.xls"))
        with open(os.path.join(dossier, "cr.csv"), "w", newline="", encoding="cp1252",
                  errors="replace") as f:
            w = csv.writer(f, delimiter=";")
            for r in rows:
                w.writerow([_fr(v).replace(" ", "") if isinstance(v, (int, float)) else _fr(v)
                            for v in r])
        doc = SimpleDocTemplate(os.path.join(dossier, "cr.pdf"), pagesize=landscape(A4))
        t = Table([[_fr(v) for v in r] for r in rows if any(v is not None for v in r)])
        t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                               ("FONTSIZE", (0, 0), (-1, -1), 6)]))
        doc.build([t])
        for ext in ("xls", "csv", "pdf"):
            autre = _lignes(os.path.join(dossier, f"cr.{ext}"))
            assert set(autre) == set(ref), (ext, set(ref) ^ set(autre))
            ecarts = [k for k in ref if abs(ref[k] - autre[k]) > 0.011]
            assert not ecarts, (ext, ecarts[:3])
    finally:
        shutil.rmtree(dossier, ignore_errors=True)


def _classeur(entete, lignes, dossier, nom="cr.xlsx"):
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Feuil2"
    ws.append([None])
    ws.append(["SITUATION COMPTE D'EXPLOITATION  JANVIER 2025"])
    ws.append(entete)
    for l in lignes:
        ws.append(l)
    p = os.path.join(dossier, nom)
    wb.save(p)
    return p


def test_en_tetes_nombre_agences_variable():
    from engine.import_compte_resultat_agence import importer_compte_resultat
    dossier = tempfile.mkdtemp()
    try:
        # 4 agences + MICROPOP, puis le mois précédent recopié à droite (à ignorer)
        p = _classeur(["INTITULE", "VICTOIRE ", "OZONE", "GOMA", "LUBUMBASHI", "MICROPOP", None,
                       "SITUATION DECEMBRE 2024"],
                      [["TOTAL PRODUITS", 10, 20, 30, 40, 100, None, 999],
                       ["RESULTAT  COMPTABLE", 1, -2, 3, 4, 6, None, 555]], dossier)
        r = importer_compte_resultat(p, dt.date(2025, 1, 31))
        assert r["agences"] == ["AGENCE DE VICTOIRE", "AGENCE OZONE", "AGENCE DE GOMA",
                                "AGENCE DE LUBUMBASHI"], r["agences"]
        assert r["nb_alertes"] == 0 and r["nb_lignes"] == 8
        assert {l["poste"] for l in r["lignes"]} == {"TOTAL PRODUITS", "RESULTAT COMPTABLE"}
        # colonne d'agence inconnue → refus
        p = _classeur(["INTITULE", "VICTOIRE", "KINSHASA NORD", "MICROPOP"],
                      [["TOTAL PRODUITS", 1, 2, 3]], dossier, "inconnue.xlsx")
        try:
            importer_compte_resultat(p, dt.date(2025, 1, 31))
            raise AssertionError("agence inconnue acceptée")
        except ValueError as e:
            assert "inconnue" in str(e)
        # MICROPOP vide alors que les agences ne le sont pas → alerte (plus de saut silencieux)
        p = _classeur(["INTITULE", "VICTOIRE", "OZONE", "MICROPOP"],
                      [["TOTAL PRODUITS", 5, 5, None]], dossier, "vide.xlsx")
        assert importer_compte_resultat(p, dt.date(2025, 1, 31))["nb_alertes"] == 1
        # pas d'en-tête MICROPOP → refus
        p = _classeur(["INTITULE", "VICTOIRE", "OZONE", "TOTAL"],
                      [["TOTAL PRODUITS", 5, 5, 10]], dossier, "sans.xlsx")
        try:
            importer_compte_resultat(p, dt.date(2025, 1, 31))
            raise AssertionError("fichier sans MICROPOP accepté")
        except ValueError as e:
            assert "MICROPOP" in str(e)
    finally:
        shutil.rmtree(dossier, ignore_errors=True)


def _demande(format, n=2):
    import export_tableaux as E
    return E.DemandeExport(
        titre="Compte d'exploitation par agence", sous_titre="Situation au 31 juillet 2026",
        nom="PopPilot_compte_exploitation_2026-07-31", format=format,
        sections=[E.Section(titre="Postes", colonnes=[
            E.Colonne(libelle="Poste", cle="poste"), E.Colonne(libelle="Victoire", cle="AGENCE DE VICTOIRE"),
            E.Colonne(libelle="MICROPOP", cle="__total")],
            lignes=[{"poste": f"P{i}", "AGENCE DE VICTOIRE": -12498.93 + i, "__total": 24798.8}
                    for i in range(n)]),
            E.Section(titre="Direction generale", colonnes=[
                E.Colonne(libelle="Fonction", cle="fonction"), E.Colonne(libelle="Prime", cle="prime")],
                lignes=[{"fonction": "DG", "prime": 247.99}])])


def test_export_sections_trois_formats():
    import openpyxl
    import export_tableaux as E
    from fastapi import HTTPException
    u = {"role": "CDG", "login": "cdg"}
    r = E.export_sections(_demande("csv"), u)
    texte = r.body.decode("utf-8")
    assert texte.startswith("﻿PopPilot — Compte d'exploitation")
    assert "Poste;Victoire;MICROPOP" in texte and "P0;-12498,93;24798,80" in texte
    assert 'filename="PopPilot_compte_exploitation_2026-07-31.csv"' in r.headers["content-disposition"]
    r = E.export_sections(_demande("xlsx"), u)
    wb = openpyxl.load_workbook(io.BytesIO(r.body))
    assert wb.sheetnames == ["Postes", "Direction generale"], wb.sheetnames
    valeurs = [c for row in wb["Postes"].iter_rows(values_only=True) for c in row]
    assert -12498.93 in valeurs                              # un vrai nombre, pas du texte
    r = E.export_sections(_demande("pdf", n=400), u)         # plusieurs pages
    assert r.body[:5] == b"%PDF-" and r.media_type == "application/pdf"
    for mauvais, code in ((_demande("doc"), 422),):
        try:
            E.export_sections(mauvais, u)
            raise AssertionError("format inconnu accepté")
        except HTTPException as e:
            assert e.status_code == code
    ancien, E.MAX_LIGNES = E.MAX_LIGNES, 10
    try:
        E.export_sections(_demande("csv", n=20), u)
        raise AssertionError("export démesuré accepté")
    except HTTPException as e:
        assert e.status_code == 413
    finally:
        E.MAX_LIGNES = ancien


def test_taux_chronologiques_filtres_et_exports():
    import openpyxl
    import taux as T
    from fastapi import HTTPException
    from socle.schema import ParamTauxChange, fermer_moteurs, get_session, init_db
    db = "socle/test_taux_liste.db"
    fermer_moteurs()
    if os.path.exists(db):
        os.remove(db)
    init_db(db)
    s = get_session(db)
    for d, t in ((dt.date(2026, 8, 31), 2263.43), (dt.date(2026, 7, 31), 2268.75),
                 (dt.date(2026, 9, 24), 2268.05), (dt.date(2026, 6, 30), 2259.4)):
        s.add(ParamTauxChange(date_effet=d, devise_source="USD", devise_cible="CDF", taux=t))
    s.commit()
    s.close()
    origine = T.lister_taux
    T.lister_taux = lambda d, f, db_path=None: origine(d, f, db)
    try:
        tous = T.endpoint_taux(debut=None, fin=None, user={"role": "AGENCE"})
        assert [x["date"] for x in tous["taux"]] == ["2026-06-30", "2026-07-31", "2026-08-31",
                                                     "2026-09-24"]           # chronologique
        f = T.endpoint_taux(debut="2026-07-01", fin="2026-08-31", user={"role": "AGENCE"})
        assert [x["taux"] for x in f["taux"]] == [2268.75, 2263.43]
        u = {"role": "CDG", "login": "cdg"}
        csv_ = T.export_taux(debut="2026-07-01", fin="2026-08-31", format="csv", user=u).body.decode("utf-8")
        assert "2026-07-31;2268,75" in csv_ and "2026-09-24" not in csv_ and "2026-06-30" not in csv_
        wb = openpyxl.load_workbook(io.BytesIO(T.export_taux(debut="2026-07-01", fin="2026-08-31",
                                                              format="xlsx", user=u).body))
        assert [c for row in wb.active.iter_rows(values_only=True) for c in row].count(2263.43) == 1
        assert T.export_taux(debut=None, fin=None, format="pdf", user=u).body[:5] == b"%PDF-"
        try:
            T.endpoint_taux(debut="2026-09-01", fin="2026-08-01", user=u)
            raise AssertionError("période inversée acceptée")
        except HTTPException as e:
            assert e.status_code == 422
    finally:
        T.lister_taux = origine
        fermer_moteurs()


if __name__ == "__main__":
    code = D.lancer("Imports multi-formats et exports", [
        (test_compte_resultat_tous_formats,
         "Compte de résultat : xlsx = xls = csv = pdf (174 lignes, Σ 24 798,80)"),
        (test_en_tetes_nombre_agences_variable,
         "En-têtes : 4 agences, colonnes après MICROPOP ignorées, agence inconnue refusée"),
        (test_export_sections_trois_formats, "Exports CSV / Excel / PDF ; 422 ; 413"),
        (test_taux_chronologiques_filtres_et_exports,
         "Taux : ordre chronologique, filtre début/fin, exports filtrés"),
    ])
    D.sortir(code)
