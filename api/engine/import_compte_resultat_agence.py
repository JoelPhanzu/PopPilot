"""
Moteur : import du compte de résultat par agence (chantier 3).
Source : fichier mensuel "COMPTE_RESULTAT_<mois>_isolé.xlsx", feuille Feuil2.
Structure FIXE :
  - colonne A (1) = intitulé du poste
  - colonnes B..G (2..7) = agences : VICTOIRE, OZONE, GOMA, LUBUMBASHI, MASINA, GOMBE
  - colonne H (8) = MICROPOP (consolidé)
  - lignes clés : "TOTAL PRODUITS", "TOTAL CHARGES", "RESULTAT COMPTABLE"
Charge dans une table compte_resultat_agence (poste × agence × mois), historisée.
CONTRÔLE : la colonne MICROPOP doit égaler la somme des 6 agences (sinon alerte).
"""
from __future__ import annotations
import datetime as dt
import openpyxl

AGENCES_COLS = {2: "AGENCE DE VICTOIRE", 3: "AGENCE OZONE", 4: "AGENCE DE GOMA",
                5: "AGENCE DE LUBUMBASHI", 6: "AGENCE DE MASINA", 7: "AGENCE DE GOMBE"}
COL_CONSOLIDE = 8  # MICROPOP


def _f(v):
    if v in (None, ""):
        return 0.0
    try:
        return float(str(v).replace(",", ".").replace("\xa0", "").replace(" ", ""))
    except (ValueError, TypeError):
        return 0.0


def importer_compte_resultat(path, date_arrete: dt.date, feuille="Feuil2",
                             tolerance=1.0):
    """Renvoie la liste des lignes (poste, agence, montant) + un rapport de contrôle.
    À adapter pour écrire dans la table compte_resultat_agence de Supabase."""
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb[feuille] if feuille in wb.sheetnames else wb.worksheets[0]

    lignes = []
    controles = []
    for row in ws.iter_rows(values_only=True):
        intitule = row[0]
        if not intitule or not str(intitule).strip():
            continue
        intitule = str(intitule).strip()
        if intitule.upper() in ("INTITULE",) or "SITUATION" in intitule.upper():
            continue  # en-têtes
        # montants par agence
        somme_agences = 0.0
        for col, agence in AGENCES_COLS.items():
            montant = _f(row[col - 1]) if len(row) >= col else 0.0
            lignes.append({"date_arrete": date_arrete, "poste": intitule,
                           "agence": agence, "montant": montant})
            somme_agences += montant
        # contrôle : consolidé = somme des agences
        consolide = _f(row[COL_CONSOLIDE - 1]) if len(row) >= COL_CONSOLIDE else 0.0
        if consolide and abs(consolide - somme_agences) > tolerance:
            controles.append({"poste": intitule, "consolide": consolide,
                              "somme_agences": somme_agences,
                              "ecart": consolide - somme_agences})
    return {"lignes": lignes, "controles_incoherents": controles,
            "nb_lignes": len(lignes), "nb_alertes": len(controles)}


def resultat_par_agence(lignes):
    """Extrait le RÉSULTAT COMPTABLE par agence depuis les lignes importées."""
    res = {}
    for l in lignes:
        if "RESULTAT" in l["poste"].upper() and "COMPTABLE" in l["poste"].upper():
            res[l["agence"]] = l["montant"]
    return res


if __name__ == "__main__":
    import sys
    r = importer_compte_resultat(sys.argv[1], dt.date(2026, 7, 31))
    print(f"Lignes importées : {r['nb_lignes']} | alertes de cohérence : {r['nb_alertes']}")
    res = resultat_par_agence(r["lignes"])
    print("\nRÉSULTAT COMPTABLE par agence :")
    for ag, m in sorted(res.items(), key=lambda x: -x[1]):
        print(f"  {ag:26s} : {m:>14,.2f}  {'bénéfice' if m >= 0 else 'PERTE'}")
