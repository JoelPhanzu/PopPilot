"""
Moteur de dérivation (Lot 1.2) — CLAUDE.md §6, §4.4, Livrable 2 (PV-*, CR-CROIS).

Recalcule, à partir du brut stocké (jamais stocké lui-même) :
  - taux de provision par prêt (barème daté §4.4)
  - provision capital = encours × taux (seule retenue, BCC)
  - croissance du portefeuille = encours(M) / encours(M-1) − 1
Le barème est lu depuis param_bareme_provision à la date d'effet ≤ date_arrete.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import select

from socle.schema import FaitCredit, ParamBaremeProvision, get_session


def charger_bareme(session, date_arrete: dt.date):
    """Barème en vigueur à la date d'arrêté (date d'effet la plus récente ≤ arrêté)."""
    date_effet = session.execute(
        select(ParamBaremeProvision.date_effet)
        .where(ParamBaremeProvision.date_effet <= date_arrete)
        .order_by(ParamBaremeProvision.date_effet.desc())
    ).scalars().first()
    if date_effet is None:
        raise ValueError(f"Aucun barème de provision en vigueur au {date_arrete} (§18.4 H-2).")
    tranches = session.execute(
        select(ParamBaremeProvision).where(ParamBaremeProvision.date_effet == date_effet)
    ).scalars().all()
    return sorted(tranches, key=lambda t: t.min_jours)


def taux_provision(bareme, jours_retard: int) -> tuple[float, int, str]:
    """(taux, code, tranche) pour un nombre de jours de retard donné."""
    for t in bareme:
        mx = t.max_jours if t.max_jours is not None else 10**9
        if t.min_jours <= jours_retard <= mx:
            return t.taux, t.code, t.tranche
    return 0.0, 0, "Sain"


def deriver_provisions(date_arrete: dt.date, db_path="socle/micropop.db") -> dict:
    """Calcule provision capital totale + par agence.
    - Barème normal (§4.4) appliqué à TOUS les prêts, Goma incluse (une partie de la provision de
      Goma vient bien de l'encours en retard résiduel).
    - Provision MANUELLE (DAF) : complément saisi qui S'AJOUTE au barème pour l'agence concernée
      (ex. Goma : part barème + complément 1 % cumulé validé DAF)."""
    from socle.schema import ProvisionManuelle
    s = get_session(db_path)
    bareme = charger_bareme(s, date_arrete)

    manuelles = {}
    for pm in s.execute(
        select(ProvisionManuelle).where(ProvisionManuelle.date_arrete == date_arrete)
    ).scalars().all():
        manuelles[pm.agence.strip().upper()] = (pm.montant, pm.note)

    # Seules colonnes lues ci-dessous (lignes SQL simples : ~10x plus rapide que les
    # objets ORM complets de 36 colonnes depuis Supabase — mêmes chiffres).
    prets = s.execute(
        select(FaitCredit.agence, FaitCredit.encours, FaitCredit.jours_de_retard)
        .where(FaitCredit.date_arrete == date_arrete)
    ).all()
    s.close()

    total = 0.0
    par_agence: dict[str, float] = {}
    par_agence_bareme: dict[str, float] = {}
    par_tranche: dict[str, float] = {}
    detail_manuel: dict[str, str] = {}

    # 1) barème automatique — appliqué à TOUS les prêts (Goma comprise)
    for p in prets:
        taux, code, tranche = taux_provision(bareme, p.jours_de_retard or 0)
        prov = (p.encours or 0.0) * taux
        total += prov
        par_agence[p.agence] = par_agence.get(p.agence, 0.0) + prov
        par_agence_bareme[p.agence] = par_agence_bareme.get(p.agence, 0.0) + prov
        par_tranche[tranche] = par_tranche.get(tranche, 0.0) + prov

    # 2) complément manuel (DAF) — S'AJOUTE au barème de l'agence
    for ag_maj, (montant, note) in manuelles.items():
        total += montant
        libelle_ag = next((p.agence for p in prets
                           if (p.agence or "").strip().upper() == ag_maj), ag_maj)
        par_agence[libelle_ag] = par_agence.get(libelle_ag, 0.0) + montant
        par_tranche["Complément manuel"] = par_tranche.get("Complément manuel", 0.0) + montant
        detail_manuel[libelle_ag] = note or ""

    return {"provision_capital_totale": total, "par_agence": par_agence,
            "par_agence_bareme": par_agence_bareme,
            "par_tranche": par_tranche, "provisions_manuelles": detail_manuel}


def croissance_portefeuille(date_arrete: dt.date, date_arrete_precedent: dt.date,
                            db_path="socle/micropop.db") -> dict:
    """Croissance = encours(arrêté) / encours(arrêté précédent) − 1, global et par agence."""
    s = get_session(db_path)

    def encours_par_agence(d):
        rows = s.execute(select(FaitCredit.agence, FaitCredit.encours)
                         .where(FaitCredit.date_arrete == d)).all()
        out = {"__global__": 0.0}
        for p in rows:
            out["__global__"] += p.encours or 0.0
            out[p.agence] = out.get(p.agence, 0.0) + (p.encours or 0.0)
        return out

    cur = encours_par_agence(date_arrete)
    prev = encours_par_agence(date_arrete_precedent)
    s.close()

    res = {}
    for k, v in cur.items():
        base = prev.get(k, 0.0)
        res[k] = (v / base - 1) if base else None
    return {"global": res.get("__global__"), "detail": res,
            "encours_courant": cur["__global__"], "encours_precedent": prev["__global__"]}


if __name__ == "__main__":
    prov = deriver_provisions(dt.date(2026, 5, 30))
    print(f"Provision capital totale (mai) : {prov['provision_capital_totale']:,.2f}")
    for tr, v in sorted(prov["par_tranche"].items()):
        print(f"  {tr:14s} {v:12,.2f}")
    cr = croissance_portefeuille(dt.date(2026, 5, 30), dt.date(2026, 4, 30))
    print(f"\nCroissance globale mai vs avril : {cr['global']:.4%}")
