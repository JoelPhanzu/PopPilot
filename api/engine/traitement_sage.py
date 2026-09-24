"""
Moteur : traitement du Grand Livre CBS pour importation dans SAGE (chantier 5).

ENTRÉE  : fichier CBS brut (feuille type "Grand_livre") — 9 colonnes :
          Compte | Libelle compte | Sens (c/d) | Devise | Montant Total |
          Date Comptable | Opération | Utilisateur | Guichet
SORTIE  : fichier au format SAGE (12 colonnes, ordre exact) :
          Date Comptable | N° Pièce | Code journal | CG | Libelle compte | Devise |
          Parité | Montant devise | Débit CDF | Crédit CDF | N° Section | Type_Ecriture

RÈGLES (validées avec le CDG) :
1. Reformatage du compte (CG) : retirer les points, remplacer suffixe devise USD→0 / CDF→1,
   compléter à 8 chiffres par des zéros à droite.  ex. "3.2.5.0.3" (USD) -> "32503000"
2. Conversion CDF : SAGE tient la compta en CDF.
   - Montant devise = montant d'origine (tel quel).
   - Parité = taux du mois (unique, saisi ; même logique que FINA/AML, param_taux_change daté).
   - Montant CDF = montant × taux si USD ; = montant tel quel si déjà CDF (parité 1).
   - Sens 'd' -> Débit CDF ; sens 'c' -> Crédit CDF (l'autre colonne reste vide).
3. Colonnes laissées vides (SAGE les gère à l'import) : N° Pièce, Code journal, N° Section.
4. Type_Ecriture = "G" (écriture générale) pour toutes les lignes.

STRICTEMENT ADDITIF : moteur autonome, ne touche à rien d'existant.
"""
from __future__ import annotations
import datetime as dt
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment

COLS_ENTREE = ["compte", "libelle", "sens", "devise", "montant",
               "date", "operation", "utilisateur", "guichet"]

COLS_SAGE = ["Date Comptable", "N° Pièce", "Code journal", "CG", "Libelle compte",
             "Devise", "Parité", "Montant devise", "Débit CDF", " Crédit CDF ",
             " N° Section ", "Type_Ecriture"]


def _f(v):
    if v in (None, ""):
        return 0.0
    try:
        return float(str(v).replace(",", ".").replace("\xa0", "").replace(" ", ""))
    except (ValueError, TypeError):
        return 0.0


def reformater_compte(compte: str, devise: str) -> str:
    """'3.2.5.0.3' + devise -> '32503000' (8 chiffres, suffixe 0=USD / 1=CDF)."""
    base = str(compte).replace(".", "").strip()
    suffixe = "0" if str(devise).strip().upper() == "USD" else "1"
    cg = base + suffixe
    # compléter à 8 chiffres par des zéros à droite
    if len(cg) < 8:
        cg = cg + "0" * (8 - len(cg))
    return cg[:8]


def traiter_gl_pour_sage(chemin_entree, taux_cdf, feuille=None, taux_du_jour=None):
    """Transforme le GL CBS en lignes au format SAGE. taux_cdf = taux du mois (USD->CDF).

    taux_du_jour (optionnel) : fonction date_comptable -> taux. Le taux est JOURNALIER
    (confirmé CDG) : fournie, elle remplace taux_cdf ligne par ligne pour les lignes USD.
    Absente, le comportement d'origine (taux unique) est inchangé."""
    wb = openpyxl.load_workbook(chemin_entree, read_only=True, data_only=True)
    ws = wb[feuille] if (feuille and feuille in wb.sheetnames) else wb.worksheets[0]

    lignes_sage = []
    total_debit = total_credit = 0.0
    n_usd = n_cdf = 0
    for row in ws.iter_rows(min_row=2, values_only=True):
        if not row[0]:  # pas de compte -> ligne vide
            continue
        compte, libelle, sens, devise, montant = row[0], row[1], row[2], row[3], _f(row[4])
        date_c, operation = row[5], row[6]
        devise = str(devise).strip().upper() if devise else "USD"
        sens = str(sens).strip().lower() if sens else ""

        cg = reformater_compte(compte, devise)
        taux = taux_du_jour(date_c) if (taux_du_jour and devise == "USD") else taux_cdf
        parite = taux if devise == "USD" else 1
        montant_cdf = montant * taux if devise == "USD" else montant
        if devise == "USD":
            n_usd += 1
        else:
            n_cdf += 1

        debit = round(montant_cdf, 2) if sens == "d" else None
        credit = round(montant_cdf, 2) if sens == "c" else None
        if debit:
            total_debit += debit
        if credit:
            total_credit += credit

        lignes_sage.append([
            date_c, None, None, cg, libelle, devise,
            parite, round(montant, 2), debit, credit, None, "G",
        ])

    return {
        "lignes": lignes_sage,
        "nb_lignes": len(lignes_sage),
        "total_debit_cdf": total_debit,
        "total_credit_cdf": total_credit,
        "ecart_equilibre": round(total_debit - total_credit, 2),
        "nb_usd": n_usd, "nb_cdf": n_cdf,
    }


def ecrire_fichier_sage(resultat, chemin_sortie):
    """Écrit les lignes SAGE dans un .xlsx propre, prêt à importer."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "GL SAGE"
    entete = Font(bold=True, color="FFFFFF")
    fond = PatternFill("solid", fgColor="0B3D5C")
    for c, titre in enumerate(COLS_SAGE, 1):
        cell = ws.cell(row=1, column=c, value=titre.strip())
        cell.font = entete
        cell.fill = fond
        cell.alignment = Alignment(horizontal="center")
    for r, ligne in enumerate(resultat["lignes"], 2):
        for c, val in enumerate(ligne, 1):
            ws.cell(row=r, column=c, value=val)
    # largeurs
    for c, w in enumerate([14, 10, 11, 12, 34, 8, 10, 15, 16, 16, 11, 12], 1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(c)].width = w
    wb.save(chemin_sortie)
    return chemin_sortie


if __name__ == "__main__":
    import sys
    src = sys.argv[1]
    taux = float(sys.argv[2]) if len(sys.argv) > 2 else 2365.0
    r = traiter_gl_pour_sage(src, taux)
    print(f"Lignes traitées : {r['nb_lignes']}  (USD {r['nb_usd']}, CDF {r['nb_cdf']})")
    print(f"Total Débit CDF  : {r['total_debit_cdf']:,.2f}")
    print(f"Total Crédit CDF : {r['total_credit_cdf']:,.2f}")
    print(f"Écart débit-crédit : {r['ecart_equilibre']:,.2f}")
    out = ecrire_fichier_sage(r, "/tmp/GL_SAGE_genere.xlsx")
    print("Fichier généré :", out)
