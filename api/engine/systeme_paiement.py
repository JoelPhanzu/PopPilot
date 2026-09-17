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


def transactions_inventaire(path_inventaire, taux_cdf=None):
    """Versement (dépôts) / retrait depuis l'inventaire, nombre + montant, par DEVISE SÉPARÉE.

    LECTURE PAR NOM DE COLONNE (devise, montant_depot, montant_retrait). Auparavant, ce
    moteur lisait les colonnes 23 et 24 pendant que l'AML lisait les colonnes 22 et 23 du
    MÊME fichier : sur l'inventaire de juillet, ce décalage d'un cran faisait compter les
    retraits comme des versements et le solde de fin comme des retraits. Le CBS déplace
    ses colonnes d'un mois à l'autre ; seuls les en-têtes sont stables.

    Le rapport BCC veut les devises SÉPARÉES (pas de conversion) — c'est ce que portent
    `valeur_cdf_native` et `valeur_usd`. Le total converti n'est calculé que si un taux
    est fourni ; sans taux, il vaut None au lieu d'un montant faux.
    """
    from ingest.import_epargne import lignes_inventaire, verifier_colonnes
    res = {"versement": {"CDF": [0, 0.0], "USD": [0, 0.0]},
           "retrait": {"CDF": [0, 0.0], "USD": [0, 0.0]}}
    premiere = True
    for row in lignes_inventaire(path_inventaire):
        if premiere:
            verifier_colonnes(row, ("devise", "montant_depot", "montant_retrait"))
            premiere = False
        devise = "USD" if str(row.get("devise") or "").strip().upper() == "USD" else "CDF"
        dep = _f(row.get("montant_depot")); ret = _f(row.get("montant_retrait"))
        if dep > 0:
            res["versement"][devise][0] += 1
            res["versement"][devise][1] += dep
        if ret > 0:
            res["retrait"][devise][0] += 1
            res["retrait"][devise][1] += ret

    def synth(bloc):
        nb_cdf, val_cdf = res[bloc]["CDF"]
        nb_usd, val_usd = res[bloc]["USD"]
        return {
            "nb_total": nb_cdf + nb_usd,
            "valeur_cdf_native": val_cdf,          # opérations déjà en CDF
            "valeur_usd": val_usd,                 # opérations en USD (montant USD)
            "valeur_usd_en_cdf": (val_usd * taux_cdf) if taux_cdf else None,
            "valeur_totale_cdf": (val_cdf + val_usd * taux_cdf) if taux_cdf else None,
            "nb_cdf": nb_cdf, "nb_usd": nb_usd,
        }
    return {"versement": synth("versement"), "retrait": synth("retrait"), "taux": taux_cdf}


if __name__ == "__main__":
    import os
    import sys
    # Démo : fichiers pris dans le dossier de données local (POPPILOT_DONNEES ou
    # PopPilot/data_local), jamais un chemin Linux figé.
    _racine = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    _donnees = os.environ.get("POPPILOT_DONNEES") or os.path.join(_racine, "data_local")
    inv = os.path.join(_donnees, "Rapport_inventaire_depot_Aout2026_Inventaire_depot_script_.xlsx")
    dorm = os.path.join(_donnees, "Compte_dormant_aout26.xlsx")
    arrete = dt.date(2026, 8, 31)
    ca = comptes_actifs(dorm, arrete)
    print("Comptes actifs:", ca["actifs"], "| dormants:", ca["dormants"], "| seuil:", ca["seuil"])

    # Taux lu dans le socle (§42 : saisi, jamais figé). Absent → on n'invente rien :
    # le rapport BCC veut de toute façon les devises SÉPARÉES, sans conversion.
    from ingest.taux_change import taux_en_vigueur
    taux = taux_en_vigueur(arrete)
    tx = transactions_inventaire(inv, taux_cdf=taux)
    for b in ("versement", "retrait"):
        s = tx[b]
        # Sans taux, `valeur_totale_cdf` vaut None : l'ancien f"{...:,.0f}" levait alors
        # un TypeError et la démo ne rendait rien. On affiche ce qu'on a — les deux
        # devises natives, qui sont l'attendu du rapport — et le total seulement s'il existe.
        total = (f"{s['valeur_totale_cdf']:,.0f}" if s["valeur_totale_cdf"] is not None
                 else "n/a (aucun taux saisi — devises non converties)")
        print(f"{b}: {s['nb_total']} ops | CDF natif {s['valeur_cdf_native']:,.0f} "
              f"({s['nb_cdf']}) | USD {s['valeur_usd']:,.0f} ({s['nb_usd']}) "
              f"→ total CDF {total}")
