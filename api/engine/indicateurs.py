"""
Moteur des indicateurs de performance & ratios prudentiels (Phase 3) — CLAUDE.md §26-30, §67-69.

PRINCIPE CLÉ (correction CDG) : le PAR vient de la Phase 1 (extraction crédit), PAS du compte 39.
Le compte 39 de la balance = capital en retard ≥1 jour = PAR1 (impossible d'en extraire le PAR30,
classé par produit/durée, pas par ancienneté). Source unique = engine/par.py (invariant X-5).
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import select, func

from socle.schema import FaitBalance, get_session
from engine.etats_financiers import etats_financiers


def _soldes_par_compte(session, date_arrete):
    rows = session.execute(
        select(FaitBalance).where(FaitBalance.date_arrete == date_arrete)
    ).scalars().all()
    return {r.numero_compte: (r.solde_net or 0.0) for r in rows}


def _somme_prefixes(soldes, *prefixes, signe=1):
    total = 0.0
    for compte, solde in soldes.items():
        if any(str(compte).startswith(p) for p in prefixes):
            total += solde
    return signe * total


def _par_depuis_credit(date_arrete_compta, db_path):
    """PAR déjà calculé en Phase 1 (source unique). Cherche l'arrêté crédit du mois de la balance,
    sinon le plus récent avant la fin de ce mois."""
    from engine.par import calculer_par
    from socle import historisation as H
    s = get_session(db_path)
    y, m = date_arrete_compta.year, date_arrete_compta.month
    fin_mois = dt.date(y + (m == 12), (m % 12) + 1, 1) - dt.timedelta(days=1)
    d_credit, _ = H.snapshot_le_plus_recent(s, "credit", fin_mois)
    s.close()
    if d_credit is None:
        return None
    r = calculer_par(d_credit, db_path=db_path)
    return {"date_credit": d_credit,
            "meme_mois": (d_credit.month == m and d_credit.year == y),
            "par1": r["global"].par1, "par30": r["global"].par30,
            "par90": r["global"].par90, "encours": r["global"].encours}


def _agregats_bilan(soldes, ef):
    """Agrégats de bilan à une date (pour moyennes de période)."""
    portefeuille = _somme_prefixes(soldes, "31", "32", "39")
    fp_base = -_somme_prefixes(soldes, "10", "11", "12", "13", "14")
    return {"portefeuille": portefeuille, "fonds_propres_base": fp_base,
            "total_actif": ef["total_actif"]}


def indicateurs_prudentiels(date_arrete, date_debut_exercice=None, db_path="socle/micropop.db"):
    s = get_session(db_path)
    soldes = _soldes_par_compte(s, date_arrete)
    s.close()
    if not soldes:
        raise ValueError(f"Aucune balance pour {date_arrete}.")

    ef = etats_financiers(date_arrete, db_path=db_path)

    portefeuille_brut = _somme_prefixes(soldes, "31", "32", "39")
    capital_retard_39 = _somme_prefixes(soldes, "39")                 # = PAR1 (bilan)
    immob_nettes = _somme_prefixes(soldes, "20", "22", "23", "24", "25", "26") \
        + _somme_prefixes(soldes, "28")                              # 28 amort (négatif)
    depots_cautionnements_27 = _somme_prefixes(soldes, "27")
    disponibles = _somme_prefixes(soldes, "56", "57")                # toute la trésorerie (CDG)
    total_actif = ef["total_actif"]
    # Fonds propres de base = comptes 10,11,12,13,14 (résultat NON affecté) — pilote TOUS les ratios
    fonds_propres_base = -_somme_prefixes(soldes, "10", "11", "12", "13", "14")
    # Fonds propres prudentiels = base + compte 18 (confirmé CDG)
    provisions_18 = -_somme_prefixes(soldes, "18")
    fonds_propres_prudentiels = fonds_propres_base + provisions_18
    resultat = ef["resultat_net"]
    # VERSION INFORMATIVE (résultat de l'exercice affecté) — n'entre PAS dans les ratios
    fonds_propres_base_avec_resultat = fonds_propres_base + resultat
    fonds_propres_prudentiels_avec_resultat = fonds_propres_prudentiels + resultat
    produits = ef["produits"]
    charges = ef["charges"]
    charges_personnel = _somme_prefixes(soldes, "66")
    interets_produits = -_somme_prefixes(soldes, "70", "71", "72")

    # ── Moyennes de période : (arrêté + début exercice)/2 (§29-7) ──
    # début exercice = 31/12 de l'année précédente si présent en base
    if date_debut_exercice is None:
        date_debut_exercice = dt.date(date_arrete.year - 1, 12, 31)
    portefeuille_moyen = portefeuille_brut
    fonds_propres_moyens = fonds_propres_base
    actif_moyen = total_actif
    moyennes_dispo = False
    try:
        s2 = get_session(db_path)
        soldes0 = _soldes_par_compte(s2, date_debut_exercice)
        s2.close()
        if soldes0:
            ef0 = etats_financiers(date_debut_exercice, db_path=db_path)
            ag0 = _agregats_bilan(soldes0, ef0)
            portefeuille_moyen = (portefeuille_brut + ag0["portefeuille"]) / 2
            fonds_propres_moyens = (fonds_propres_base + ag0["fonds_propres_base"]) / 2
            actif_moyen = (total_actif + ag0["total_actif"]) / 2
            moyennes_dispo = True
    except Exception:
        pass

    par_credit = _par_depuis_credit(date_arrete, db_path)
    par1 = par_credit["par1"] if par_credit else capital_retard_39
    par30 = par_credit["par30"] if par_credit else None

    # ── Dépôts à vue depuis l'épargne (pour liquidité E4) ──
    depots_a_vue = None
    try:
        from engine.epargne import synthese_epargne
        syn = synthese_epargne(date_arrete, db_path=db_path)
        depots_a_vue = syn["depots_a_vue"]
    except Exception:
        pass

    # ── B2 emprunteurs/agent : emprunteurs actifs (crédit) ÷ agents actifs (roster) ──
    nb_emprunteurs = nb_agents = None
    try:
        from socle.schema import FaitCredit, DimEmploye
        s3 = get_session(db_path)
        if par_credit:
            nb_emprunteurs = s3.execute(
                select(func.count(func.distinct(FaitCredit.numero_client)))
                .where(FaitCredit.date_arrete == par_credit["date_credit"])
            ).scalar_one()
        nb_agents = s3.execute(
            select(func.count()).select_from(DimEmploye)
            .where(DimEmploye.fonction == "agent_credit")
        ).scalar_one()
        s3.close()
    except Exception:
        pass

    def ratio(num, den):
        if not den or num is None:
            return None
        return num / den * 100

    ind = {}
    ind["A1_PAR30"] = {"valeur": ratio(par30, portefeuille_brut), "num": par30,
                       "den": portefeuille_brut, "norme": "< 5 %", "source": "crédit Phase 1"}
    ind["A1bis_PAR1"] = {"valeur": ratio(par1, portefeuille_brut), "num": par1,
                         "den": portefeuille_brut, "norme": "(risque global)",
                         "source": "crédit Phase 1"}
    ind["A2_abandon"] = {"valeur": ratio(0.0, portefeuille_moyen), "num": 0.0,
                         "den": portefeuille_moyen, "norme": "< 2 %"}
    ind["B1_efficacite"] = {"valeur": ratio(charges_personnel, portefeuille_moyen),
                            "num": charges_personnel, "den": portefeuille_moyen, "norme": "13-21 %"}
    # B2 : emprunteurs actifs ÷ agents — SANS ×100 (§28 B.2)
    ind["B2_emprunteurs_agent"] = {
        "valeur": (nb_emprunteurs / nb_agents) if (nb_emprunteurs and nb_agents) else None,
        "num": nb_emprunteurs, "den": nb_agents, "norme": "> 130", "sans_pourcent": True}
    ind["C1_ROE"] = {"valeur": ratio(resultat, fonds_propres_moyens), "num": resultat,
                     "den": fonds_propres_moyens, "norme": "> 15 %"}
    ind["C2_ROA"] = {"valeur": ratio(resultat, actif_moyen), "num": resultat,
                     "den": actif_moyen, "norme": "> 3 %"}
    ind["C3_rendement"] = {"valeur": ratio(interets_produits, portefeuille_moyen),
                           "num": interets_produits, "den": portefeuille_moyen, "norme": "> 15 %"}
    ind["C4_autosuffisance"] = {"valeur": ratio(produits, charges), "num": produits,
                                "den": charges, "norme": "> 119,2 %"}
    ind["D1_encaisse_oisive"] = {"valeur": ratio(disponibles, total_actif), "num": disponibles,
                                 "den": total_actif, "norme": "< 20 %"}
    ind["D2_taux_encours"] = {"valeur": ratio(portefeuille_brut, total_actif),
                              "num": portefeuille_brut, "den": total_actif, "norme": "> 70 %"}
    ind["D3_immobilisations"] = {"valeur": ratio(immob_nettes, total_actif), "num": immob_nettes,
                                 "den": total_actif, "norme": "< 10 %"}
    ind["E1_capital_min"] = {"valeur": ratio(fonds_propres_base, 700000), "num": fonds_propres_base,
                             "den": 700000, "norme": "≥ 100 %"}
    ind["E2_solvabilite"] = {"valeur": ratio(fonds_propres_prudentiels, total_actif),
                             "num": fonds_propres_prudentiels, "den": total_actif, "norme": "≥ 10 %"}
    ind["E3_capitalisation"] = {"valeur": ratio(fonds_propres_base, total_actif),
                                "num": fonds_propres_base, "den": total_actif, "norme": "≥ 15 %"}
    ind["E4_liquidite"] = {"valeur": ratio(disponibles, depots_a_vue),
                           "num": disponibles, "den": depots_a_vue, "norme": "≥ 20 %",
                           "source": "dispo bilan ÷ dépôts à vue épargne"}
    ind["E5_couverture_immob"] = {"valeur": ratio(immob_nettes, fonds_propres_prudentiels),
                                  "num": immob_nettes, "den": fonds_propres_prudentiels,
                                  "norme": "≤ 50 %"}

    return {
        "date_arrete": date_arrete, "par_credit": par_credit,
        "agregats": {
            "portefeuille_brut": portefeuille_brut, "PAR1_credit": par1, "PAR30_credit": par30,
            "capital_retard_bilan_39": capital_retard_39, "immob_nettes": immob_nettes,
            "depots_cautionnements_27": depots_cautionnements_27, "disponibles_56_57": disponibles,
            "depots_a_vue_epargne": depots_a_vue,
            "total_actif": total_actif, "fonds_propres_base": fonds_propres_base,
            "fonds_propres_prudentiels": fonds_propres_prudentiels,
            "fonds_propres_base_avec_resultat": fonds_propres_base_avec_resultat,
            "fonds_propres_prudentiels_avec_resultat": fonds_propres_prudentiels_avec_resultat,
            "resultat": resultat, "produits": produits, "charges": charges,
        },
        "indicateurs": ind,
    }


if __name__ == "__main__":
    r = indicateurs_prudentiels(dt.date(2026, 7, 31))
    print("PAR crédit:", r["par_credit"])
    for k, v in r["indicateurs"].items():
        val = f"{v['valeur']:.2f}%" if v["valeur"] is not None else "n/a"
        print(f"  {k:22s}: {val:>10s}  (norme {v['norme']})")
