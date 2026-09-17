"""
Moteur épargne (Phase Épargne) — CLAUDE.md §51, Livrable 2 catégorie E.

Encours épargne + ventilation par type de dépôt (à vue/à terme/obligatoire), devise, groupe.
Fournit le dénominateur des dépôts à vue pour la liquidité E4 (§28).
"""
from __future__ import annotations

import datetime as dt
from collections import defaultdict

from sqlalchemy import select, func

from socle.schema import FaitEpargne, get_session


def synthese_epargne(date_arrete: dt.date, db_path="socle/micropop.db",
                     en_usd=True) -> dict:
    """Synthèse épargne. Si en_usd, convertit le CDF en USD au taux de clôture (total homogène)."""
    from engine.etats_financiers import taux_change
    # try/finally OBLIGATOIRE : `taux_change` LÈVE quand aucun taux n'est saisi (§42) —
    # un cas normal, pas une panne. Le `s.close()` placé après l'appel n'était donc
    # jamais atteint et la session restait ouverte. Sous Windows le fichier SQLite
    # restait verrouillé ; sous Supabase c'est une connexion du pool (pool_size=5) qui
    # ne revient pas, à chaque calcul sur un mois dont le taux n'est pas encore saisi.
    # La fuite était invisible : les appelants enveloppent cet appel dans un
    # `except Exception` qui n'en retient que le motif.
    s = get_session(db_path)
    try:
        taux = taux_change(s, date_arrete) if en_usd else 1.0
        rows = s.execute(
            select(FaitEpargne.type_depot, FaitEpargne.devise, FaitEpargne.est_groupe,
                   func.count(), func.sum(FaitEpargne.solde_actuel))
            .where(FaitEpargne.date_arrete == date_arrete)
            .group_by(FaitEpargne.type_depot, FaitEpargne.devise, FaitEpargne.est_groupe)
        ).all()
    finally:
        s.close()
    if not rows:
        raise ValueError(f"Aucune épargne pour {date_arrete}.")

    def to_usd(solde, devise):
        if en_usd and devise == "CDF":
            return solde / taux if taux else 0.0
        return solde

    par_type = defaultdict(float)
    par_devise = defaultdict(float)          # en devise d'origine (lisibilité)
    par_type_devise = defaultdict(float)
    groupe = 0.0
    total = 0.0
    nb = 0
    for type_depot, devise, est_groupe, count, solde in rows:
        solde = solde or 0.0
        v = to_usd(solde, devise)
        par_type[type_depot] += v
        par_devise[devise] += solde
        par_type_devise[(type_depot, devise)] += solde
        if est_groupe:
            groupe += v
        total += v
        nb += count

    return {
        "date_arrete": date_arrete, "devise_totaux": "USD" if en_usd else "origine",
        "taux_change": taux,
        "encours_total": total,
        "nb_comptes": nb,
        "par_type": dict(par_type),
        "par_devise_origine": dict(par_devise),
        "par_type_devise": {f"{t}/{d}": v for (t, d), v in par_type_devise.items()},
        "epargne_groupe": groupe,
        "depots_a_vue": par_type.get("a_vue", 0.0),
        "depots_a_terme": par_type.get("a_terme", 0.0),
        "depots_obligatoire": par_type.get("obligatoire", 0.0),
    }


def nb_epargnants(date_arrete: dt.date, db_path="socle/micropop.db") -> int:
    """Nombre d'épargnants = clients distincts avec au moins un compte."""
    s = get_session(db_path)
    try:
        n = s.execute(
            select(func.count(func.distinct(FaitEpargne.id_client)))
            .where(FaitEpargne.date_arrete == date_arrete)
        ).scalar_one()
    finally:
        s.close()
    return n


if __name__ == "__main__":
    r = synthese_epargne(dt.date(2026, 7, 31))
    print(f"Encours épargne total : {r['encours_total']:,.2f} ({r['nb_comptes']:,} comptes)")
    print(f"Épargnants : {nb_epargnants(dt.date(2026,7,31)):,}")
    print("\nPar type de dépôt :")
    for t, v in r["par_type"].items():
        print(f"  {t:14s}: {v:>18,.2f}")
    print(f"\nDépôts à vue (dénominateur liquidité E4) : {r['depots_a_vue']:,.2f}")
    print(f"Épargne groupe : {r['epargne_groupe']:,.2f}")
    print("\nPar devise :")
    for d, v in r["par_devise"].items():
        print(f"  {d}: {v:,.2f}")
