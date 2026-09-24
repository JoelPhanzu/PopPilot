"""
Moteur décaissement & orphelins (Lots 1.5, 1.6) — CLAUDE.md §7.3, §15.3, §18.1, §18.2.

Décaissement : filtre par INTERVALLE [date_debut ; date_fin] sur date_deboursement (§18.1).
  Défaut : 1er du mois de l'arrêté → date d'arrêté.
Orphelins : prêt dont l'agent (ou superviseur) n'est pas au roster de la date d'effet (§18.2).
  Portefeuille orphelin nommé par l'agence du fichier SIG.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import select

from socle.schema import FaitCredit, DimEmploye, get_session


# ─── Décaissement (Lot 1.5) ───────────────────────────────────────────────────
def decaissements(date_arrete: dt.date, date_debut: dt.date | None = None,
                  date_fin: dt.date | None = None, db_path="socle/micropop.db") -> dict:
    """Nombre et volume décaissés sur [date_debut ; date_fin], par agence et global.
    Défaut : du 1er du mois de l'arrêté à la date d'arrêté."""
    if date_fin is None:
        date_fin = date_arrete
    if date_debut is None:
        date_debut = date_arrete.replace(day=1)

    s = get_session(db_path)
    # Seules colonnes lues ci-dessous (lignes SQL simples : ~10x plus rapide que les
    # objets ORM complets de 36 colonnes depuis Supabase — mêmes chiffres).
    prets = s.execute(
        select(FaitCredit.agence, FaitCredit.date_deboursement, FaitCredit.montant_debourse)
        .where(FaitCredit.date_arrete == date_arrete)
    ).all()
    s.close()

    glob_nb, glob_vol = 0, 0.0
    par_agence: dict[str, list] = {}
    for p in prets:
        dd = p.date_deboursement
        if dd and date_debut <= dd <= date_fin:
            glob_nb += 1
            glob_vol += p.montant_debourse or 0.0
            a = par_agence.setdefault(p.agence, [0, 0.0])
            a[0] += 1
            a[1] += p.montant_debourse or 0.0
    return {
        "periode": (date_debut, date_fin),
        "global": {"nombre": glob_nb, "volume": glob_vol},
        "par_agence": {k: {"nombre": v[0], "volume": v[1]} for k, v in par_agence.items()},
    }


# ─── Orphelins (Lot 1.6) ──────────────────────────────────────────────────────
def _roster(session, date_effet: dt.date, fonction: str) -> set[tuple[str, str]]:
    """Ensemble (nom, agence) des employés actifs à la date d'effet la plus récente ≤ date."""
    eff = session.execute(
        select(DimEmploye.date_debut)
        .where(DimEmploye.date_debut <= date_effet)
        .order_by(DimEmploye.date_debut.desc())
    ).scalars().first()
    if eff is None:
        return set()
    rows = session.execute(
        select(DimEmploye).where(DimEmploye.date_debut == eff,
                                 DimEmploye.fonction == fonction)
    ).scalars().all()
    return {(r.nom.strip().upper(), r.agence.strip().upper()) for r in rows}


def portefeuille_orphelin(date_arrete: dt.date, date_effet_roster: dt.date | None = None,
                          db_path="socle/micropop.db") -> dict:
    """Prêts dont l'agent (ou le superviseur) n'est pas au roster → orphelins, par agence.
    Les AGENCES FERMÉES sont exclues des orphelins et reportées à part (portefeuille gelé).
    date_effet_roster défaut = date_arrete."""
    if date_effet_roster is None:
        date_effet_roster = date_arrete
    from socle.agences import agences_fermees
    s = get_session(db_path)
    fermees = agences_fermees(s)
    agents_ok = _roster(s, date_effet_roster, "agent_credit")
    sup_ok = _roster(s, date_effet_roster, "superviseur")
    prets = s.execute(
        select(FaitCredit).where(FaitCredit.date_arrete == date_arrete)
    ).scalars().all()
    s.close()

    orph_agent: dict[str, list] = {}
    orph_sup: dict[str, list] = {}
    gelé: dict[str, list] = {}      # portefeuille des agences fermées
    for p in prets:
        agence_maj = (p.agence or "").strip().upper()
        # Agence fermée → portefeuille gelé, jamais orphelin (note métier)
        if agence_maj in fermees:
            g = gelé.setdefault(p.agence, [0, 0.0])
            g[0] += 1
            g[1] += p.encours or 0.0
            continue
        cle_agent = ((p.agent_credit or "").strip().upper(), agence_maj)
        cle_sup = ((p.superviseur or "").strip().upper(), agence_maj)
        if agents_ok and cle_agent not in agents_ok:
            o = orph_agent.setdefault(p.agence, [0, 0.0])
            o[0] += 1
            o[1] += p.encours or 0.0
        if sup_ok and cle_sup not in sup_ok:
            o = orph_sup.setdefault(p.agence, [0, 0.0])
            o[0] += 1
            o[1] += p.encours or 0.0

    return {
        "orphelins_agent": {f"Portefeuille Orphelin — {k}": {"nombre": v[0], "encours": v[1]}
                            for k, v in orph_agent.items()},
        "orphelins_superviseur": {f"Portefeuille Orphelin Sup. — {k}": {"nombre": v[0], "encours": v[1]}
                                  for k, v in orph_sup.items()},
        "portefeuille_gele": {f"Portefeuille gelé — {k} (agence fermée)": {"nombre": v[0], "encours": v[1]}
                              for k, v in gelé.items()},
    }


if __name__ == "__main__":
    d = decaissements(dt.date(2026, 5, 30))
    print(f"Décaissements {d['periode'][0]} → {d['periode'][1]} : "
          f"{d['global']['nombre']} prêts / {d['global']['volume']:,.2f}")
    o = portefeuille_orphelin(dt.date(2026, 5, 30), dt.date(2026, 5, 1))
    print("Orphelins agent:", {k: v['nombre'] for k, v in o['orphelins_agent'].items()})
