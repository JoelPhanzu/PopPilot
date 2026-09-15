"""
Moteur Rapport Système de Paiement (BCC) — CLAUDE.md (nouveau rapport).
Deux volets :
  - Comptes actifs/dormants (fichier compte dormant) : actif = dernière opération dans les 6 mois.
  - Types de transactions (inventaire dépôt) : versement (dépôts) / retrait, en nombre et volume,
    ventilés CDF/USD, USD converti en CDF au taux.
"""
from __future__ import annotations
import datetime as dt
import openpyxl


def _f(v):
    if v in (None, ""): return 0.0
    try: return float(str(v).replace(",", ".").replace("\xa0", "").replace(" ", ""))
    except (ValueError, TypeError): return 0.0


def _d(v):
    if isinstance(v, dt.datetime): return v.date()
    if isinstance(v, dt.date): return v
    return None


def _seuil_6_mois(date_arrete):
    """Date 6 mois avant l'arrêté (mois calendaires)."""
    m = date_arrete.month - 6
    y = date_arrete.year
    if m <= 0:
        m += 12; y -= 1
    import calendar
    jour = min(date_arrete.day, calendar.monthrange(y, m)[1])
    return dt.date(y, m, jour)


def comptes_actifs(path_dormant, date_arrete, col_date=2, col_sexe=5, col_statut=8):
    """Comptes actifs = dernière opération >= seuil 6 mois. Ventilé H/F/PM."""
    wb = openpyxl.load_workbook(path_dormant, read_only=True, data_only=True)
    ws = wb.worksheets[0]
    seuil = _seuil_6_mois(date_arrete)
    total = actifs = dormants = 0
    h = f = pm = 0
    for row in ws.iter_rows(min_row=2, values_only=True):
        d = _d(row[col_date - 1])
        if d is None:
            continue
        total += 1
        if d >= seuil:
            actifs += 1
            sexe = str(row[col_sexe - 1] or ""); statut = str(row[col_statut - 1] or "")
            if statut == "1":
                if sexe == "1": h += 1
                elif sexe == "2": f += 1
            elif statut in ("2", "4"):
                pm += 1
        else:
            dormants += 1
    return {"total": total, "actifs": actifs, "dormants": dormants,
            "actifs_hommes": h, "actifs_femmes": f, "actifs_pm": pm, "seuil": seuil}


def transactions_inventaire(path_inventaire, taux_cdf=2263.57,
                            col_devise=5, col_depot=23, col_retrait=24):
    """Versement (dépôts) / retrait depuis l'inventaire, nombre + volume, ventilé CDF/USD.
    Volume BCC = nombre d'opérations ; Valeur = montant. USD converti en CDF."""
    wb = openpyxl.load_workbook(path_inventaire, read_only=True, data_only=True)
    ws = wb.worksheets[0]
    res = {"versement": {"CDF": [0, 0.0], "USD": [0, 0.0]},
           "retrait": {"CDF": [0, 0.0], "USD": [0, 0.0]}}
    for row in ws.iter_rows(min_row=2, values_only=True):
        devise = "USD" if str(row[col_devise - 1] or "").strip().upper() == "USD" else "CDF"
        dep = _f(row[col_depot - 1]); ret = _f(row[col_retrait - 1])
        if dep > 0:
            res["versement"][devise][0] += 1
            res["versement"][devise][1] += dep
        if ret > 0:
            res["retrait"][devise][0] += 1
            res["retrait"][devise][1] += ret
    # totaux en CDF (USD converti) et en USD
    def synth(bloc):
        nb_cdf, val_cdf = res[bloc]["CDF"]
        nb_usd, val_usd = res[bloc]["USD"]
        return {
            "nb_total": nb_cdf + nb_usd,
            "valeur_cdf_native": val_cdf,          # opérations déjà en CDF
            "valeur_usd": val_usd,                 # opérations en USD (montant USD)
            "valeur_usd_en_cdf": val_usd * taux_cdf,
            "valeur_totale_cdf": val_cdf + val_usd * taux_cdf,
            "nb_cdf": nb_cdf, "nb_usd": nb_usd,
        }
    return {"versement": synth("versement"), "retrait": synth("retrait"), "taux": taux_cdf}


if __name__ == "__main__":
    import sys
    inv = "/mnt/user-data/uploads/Rapport_inventaire_depot_Aout2026_Inventaire_depot_script_.xlsx"
    dorm = "/mnt/user-data/uploads/Compte_dormant_aout26.xlsx"
    ca = comptes_actifs(dorm, dt.date(2026, 8, 31))
    print("Comptes actifs:", ca["actifs"], "| dormants:", ca["dormants"], "| seuil:", ca["seuil"])
    tx = transactions_inventaire(inv)
    for b in ("versement", "retrait"):
        s = tx[b]
        print(f"{b}: {s['nb_total']} ops | CDF natif {s['valeur_cdf_native']:,.0f} | "
              f"USD {s['valeur_usd']:,.0f} → total CDF {s['valeur_totale_cdf']:,.0f}")
