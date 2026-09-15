"""
Import budget + mapping dynamique compte→ligne budgétaire — CLAUDE.md §46-50, §61.
Le mapping est stocké dans la table mapping_budget (ÉDITABLE) : charges ET produits.
"""
from __future__ import annotations
import datetime as dt
import openpyxl
from sqlalchemy import select
from socle.schema import FaitBudget, MappingBudget, get_session, init_db


def _f(v):
    if v in (None, ""): return 0.0
    try: return float(str(v).replace(",", ".").replace("\xa0", "").replace(" ", ""))
    except (ValueError, TypeError): return 0.0


def importer_budget(path, exercice=2026, hypothese="H1",
                    feuille="CHARGES ET PRODUITS CONSOLIDE", db_path="socle/micropop.db"):
    """Importe le budget MOIS PAR MOIS (non linéaire) depuis la feuille CONSOLIDE du fichier budget.
    Les 12 mois sont en colonnes 2-7 (janv-juin) puis 9-14 (juil-déc) ; col 8 et 15 = sous-totaux (ignorés)."""
    init_db(db_path)
    s = get_session(db_path)
    s.query(FaitBudget).filter(FaitBudget.exercice == exercice,
                               FaitBudget.hypothese == hypothese).delete()
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb[feuille] if feuille in wb.sheetnames else wb.worksheets[0]
    # colonnes des 12 mois (1-based) : janv..juin = 2..7, juil..déc = 9..14
    COLS_MOIS = {1: 2, 2: 3, 3: 4, 4: 5, 5: 6, 6: 7,
                 7: 9, 8: 10, 9: 11, 10: 12, 11: 13, 12: 14}
    n = 0
    for row in ws.iter_rows(min_row=2, values_only=True):
        ligne = row[0]
        if not ligne or not str(ligne).strip():
            continue
        ligne = str(ligne).strip()
        for mois, col in COLS_MOIS.items():
            montant = _f(row[col - 1]) if len(row) >= col else 0.0
            if montant:
                s.add(FaitBudget(exercice=exercice, hypothese=hypothese,
                                 ligne_budgetaire=ligne, mois=mois,
                                 montant_budgete=montant, type="budget"))
                n += 1
    s.commit(); s.close()
    return {"lignes_importees": n}


def importer_mapping(path, feuille, sens, date_effet=None, db_path="socle/micropop.db"):
    """Charge le mapping compte→ligne depuis une feuille 'Résultat *' dans mapping_budget.
    sens = 'charge' ou 'produit'. Remplace le mapping existant du même sens+date."""
    init_db(db_path)
    s = get_session(db_path)
    if date_effet is None:
        date_effet = dt.date(2026, 1, 1)
    s.query(MappingBudget).filter(MappingBudget.sens == sens,
                                  MappingBudget.date_effet == date_effet).delete()
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb[feuille]
    n = 0
    for row in ws.iter_rows(min_row=2, values_only=True):
        compte = str(row[0] or "").strip()
        ligne = str(row[2] or "").strip()
        if compte and ligne and compte[0].isdigit():
            s.add(MappingBudget(numero_compte=compte, ligne_budgetaire=ligne,
                                sens=sens, date_effet=date_effet))
            n += 1
    s.commit(); s.close()
    return {"sens": sens, "comptes": n}


def affecter_compte(numero_compte, ligne_budgetaire, sens, date_effet=None,
                    db_path="socle/micropop.db"):
    """Ajoute ou réaffecte un compte à une ligne budgétaire (édition dynamique)."""
    init_db(db_path)
    s = get_session(db_path)
    if date_effet is None:
        date_effet = dt.date.today()
    existant = s.execute(
        select(MappingBudget).where(MappingBudget.numero_compte == numero_compte,
                                    MappingBudget.date_effet == date_effet)
    ).scalar_one_or_none()
    if existant:
        existant.ligne_budgetaire = ligne_budgetaire
        existant.sens = sens
    else:
        s.add(MappingBudget(numero_compte=numero_compte, ligne_budgetaire=ligne_budgetaire,
                            sens=sens, date_effet=date_effet))
    s.commit(); s.close()
    return {"compte": numero_compte, "ligne": ligne_budgetaire, "sens": sens}


def lire_mapping(sens=None, db_path="socle/micropop.db"):
    """Renvoie {compte: (ligne, sens)} depuis la table (dernière date d'effet par compte)."""
    s = get_session(db_path)
    q = select(MappingBudget).order_by(MappingBudget.date_effet)
    if sens:
        q = q.where(MappingBudget.sens == sens)
    rows = s.execute(q).scalars().all()
    s.close()
    mapping = {}
    for r in rows:   # dernière date d'effet gagne (ordre croissant)
        mapping[r.numero_compte] = (r.ligne_budgetaire, r.sens)
    return mapping


if __name__ == "__main__":
    import sys
    print(importer_budget(sys.argv[1]))
