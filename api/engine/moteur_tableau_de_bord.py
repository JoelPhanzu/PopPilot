"""
Moteur de tableau de bord (chantiers 1-2) — la BASE du métier.
Incarne la doctrine validée : FLUX vs STOCK, avec deux contrôles de temps indépendants.

DEUX CONTRÔLES DE TEMPS (comme défini dans la doctrine §19-21) :
  1. PÉRIODE DE FLUX [date_debut ; date_fin] : pour les indicateurs cumulatifs sur une période.
  2. DATE DE VALORISATION (une seule date) : pour les indicateurs de stock (photo à un instant).
Les deux sont INDÉPENDANTS. Un écran peut afficher les décaissements de [1/5 → 31/5]
ET l'encours au 31/5, sans confusion.

CLASSIFICATION (validée CDG) :
  FLUX (intervalle début→fin, cumulatif) :
    - décaissement (nombre + volume)
    - remboursements encaissés (capital, intérêts, commissions, pénalités)
    - migrations, coût du risque (variation de provision entre 2 dates)
    - production nouvelle, radiations
  STOCK (date unique, photo) :
    - encours, PAR1/30/90, provisions (solde)
    - nombre de clients actifs, nombre de crédits en cours
    - épargne (solde)

Se combine avec moteur_filtres (agence, agent, superviseur, sexe, produit, durée, client).
STRICTEMENT ADDITIF : réutilise les moteurs existants, n'en réécrit aucun.
"""
from __future__ import annotations
import datetime as dt

# Catégories de produit (règle CDG)
def categorie_produit(p) -> str:
    """GL (groupe) = Crédit LISANGA ; IL (individuel) = tout le reste."""
    lib = (p.produit_credit or "").strip().upper()
    return "GL" if "LISANGA" in lib else "IL"

def est_pme(p) -> bool:
    """Crédit PME = décaissement >= 15 000."""
    return (p.montant_debourse or 0) >= 15000


# --- INDICATEURS DE STOCK (à une date de valorisation) ---
def indicateurs_stock(prets):
    """prets = liste des prêts à la DATE DE VALORISATION (déjà filtrés).
    Renvoie encours, PAR, provisions solde, nb clients, nb crédits."""
    from collections import Counter
    encours = sum(p.encours or 0 for p in prets)
    par1 = sum(p.encours or 0 for p in prets if (p.jours_de_retard or 0) > 0)
    par30 = sum(p.encours or 0 for p in prets if (p.jours_de_retard or 0) > 30)
    par90 = sum(p.encours or 0 for p in prets if (p.jours_de_retard or 0) > 90)
    credits_par_client = Counter(p.numero_client for p in prets)
    nb_clients = sum(1.0 / credits_par_client[p.numero_client] for p in prets)
    return {
        "date_type": "valorisation (stock)",
        "encours": encours,
        "par1": par1, "par30": par30, "par90": par90,
        "pct_par1": par1 / encours if encours else 0,
        "pct_par30": par30 / encours if encours else 0,
        "pct_par90": par90 / encours if encours else 0,
        "nb_credits": len(prets),
        "nb_clients": round(nb_clients),
    }


# --- INDICATEURS DE FLUX (sur une période début→fin) ---
def decaissement_periode(prets, date_debut, date_fin):
    """Décaissement CUMULATIF sur [date_debut ; date_fin] (filtre sur date_deboursement).
    prets = extraction à la date de valorisation (contient l'historique des déboursements)."""
    nb = vol = 0
    par_cat = {"GL": [0, 0.0], "IL": [0, 0.0], "PME": [0, 0.0]}
    for p in prets:
        dd = p.date_deboursement
        if dd and date_debut <= dd <= date_fin:
            m = p.montant_debourse or 0
            nb += 1; vol += m
            cat = categorie_produit(p)
            par_cat[cat][0] += 1; par_cat[cat][1] += m
            if est_pme(p):
                par_cat["PME"][0] += 1; par_cat["PME"][1] += m
    return {
        "date_type": "flux (période)",
        "periode": (date_debut, date_fin),
        "nombre": nb, "volume": vol,
        "par_categorie": {k: {"nombre": v[0], "volume": v[1]} for k, v in par_cat.items()},
    }


def tableau_de_bord(prets_valorisation, date_valorisation, date_debut_flux, date_fin_flux):
    """Assemble un tableau de bord complet : stocks à la date de valo + flux sur la période.
    Les deux contrôles de temps sont indépendants (doctrine)."""
    return {
        "date_valorisation": date_valorisation,
        "periode_flux": (date_debut_flux, date_fin_flux),
        "STOCK": indicateurs_stock(prets_valorisation),
        "FLUX_decaissement": decaissement_periode(prets_valorisation, date_debut_flux, date_fin_flux),
    }


if __name__ == "__main__":
    import sys, os
    sys.path.insert(0, os.path.expanduser("~/mfi-pilotage"))
    try:
        from socle.schema import get_session, FaitCredit
        from sqlalchemy import select
        s = get_session()
        prets = s.execute(select(FaitCredit).where(
            FaitCredit.date_arrete == dt.date(2026, 5, 30))).scalars().all()
        s.close()
        tb = tableau_de_bord(prets, dt.date(2026, 5, 30), dt.date(2026, 5, 1), dt.date(2026, 5, 31))
        print("STOCK au", tb["date_valorisation"], ": encours",
              f"{tb['STOCK']['encours']:,.0f}", "PAR30", f"{tb['STOCK']['par30']:,.0f}")
        d = tb["FLUX_decaissement"]
        print("FLUX décaissement", d["periode"], ":", d["nombre"], "prêts,", f"{d['volume']:,.0f}")
        print("  dont GL:", d["par_categorie"]["GL"]["nombre"],
              "| IL:", d["par_categorie"]["IL"]["nombre"],
              "| PME (>=15k):", d["par_categorie"]["PME"]["nombre"])
    except Exception as e:
        print("(démo nécessite la base :", e, ")")
