"""
Moteur coût du risque & migrations (Lot 1.4) — CLAUDE.md §6, §7.2, §7.6, §14.

Rapproche deux arrêtés prêt par prêt (jointure sur numero_dossier) :
  - Coût du risque = Σ (provision capital[courant] − provision capital[précédent]).
  - État de chaque prêt : Migration (code monte), Récupération (code baisse), maintenu.
  - Entrée en PAR (code 0→>0) et migrations vers chaque tranche.
Le code de tranche (0..6) vient du barème (§4.4). Provision = encours × taux(jours_retard).
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import select

from socle.schema import FaitCredit, get_session
from engine.derivation import charger_bareme, taux_provision


def _index_prets(session, date_arrete):
    prets = session.execute(
        select(FaitCredit).where(FaitCredit.date_arrete == date_arrete)
    ).scalars().all()
    return {p.numero_dossier: p for p in prets}


def analyser_migrations(date_arrete: dt.date, date_arrete_precedent: dt.date,
                        db_path="socle/micropop.db") -> dict:
    s = get_session(db_path)
    bareme = charger_bareme(s, date_arrete)
    cur = _index_prets(s, date_arrete)
    prev = _index_prets(s, date_arrete_precedent)
    s.close()

    def code(p):
        return taux_provision(bareme, p.jours_de_retard or 0)[1]

    def prov(p):
        return (p.encours or 0.0) * taux_provision(bareme, p.jours_de_retard or 0)[0]

    cout_risque = 0.0
    entree_par_nb = 0
    entree_par_montant = 0.0
    # ⚠️ Le Dashboard classe les migrations par le CODE M-1 (tranche de DÉPART, col AW),
    # pas par la tranche d'arrivée. Le libellé « Migration vers X » désigne en fait le
    # groupe des prêts PARTIS de la tranche X-1 le mois précédent. On reproduit fidèlement.
    migr_depart = {0: 0.0, 1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0, 5: 0.0}
    recup_nb = 0
    recup_montant = 0.0

    for dossier, p in cur.items():
        p_prev = prev.get(dossier)
        code_cur = code(p)
        code_prev = code(p_prev) if p_prev else 0        # nouveau prêt → réf. sain
        prov_prev = prov(p_prev) if p_prev else 0.0      # Provision M-1 (0 si absent, §6)
        cout_risque += prov(p) - prov_prev

        if code_cur > code_prev:                          # Migration (dégradation)
            if code_prev == 0:                            # entrée en PAR
                entree_par_nb += 1
                entree_par_montant += p.encours or 0.0
            # montant classé selon la tranche de DÉPART (code M-1), comme le Dashboard
            if code_prev in migr_depart:
                migr_depart[code_prev] += p.encours or 0.0
        elif code_cur < code_prev:                        # Récupération (§14)
            recup_nb += 1
            recup_montant += p.encours or 0.0

    return {
        "cout_du_risque": cout_risque,
        "entree_par_nb": entree_par_nb,
        "entree_par_montant": entree_par_montant,
        # clés = libellés du Dashboard ; valeur = migrations dont le code M-1 = n
        "migration_vers": {
            "31-60": migr_depart[1], "61-90": migr_depart[2], "91-180": migr_depart[3],
            "181-360": migr_depart[4], "361+": migr_depart[5],
        },
        "recuperation_nb": recup_nb,
        "recuperation_montant": recup_montant,
    }


if __name__ == "__main__":
    r = analyser_migrations(dt.date(2026, 5, 30), dt.date(2026, 4, 30))
    print(f"Coût du risque        : {r['cout_du_risque']:,.2f}")
    print(f"# Entré dans PAR      : {r['entree_par_nb']}")
    print(f"Entré dans PAR (mnt)  : {r['entree_par_montant']:,.2f}")
    for tr, v in r["migration_vers"].items():
        print(f"  Migration → {tr:8s}: {v:,.2f}")
    print(f"Récupération (#/mnt)  : {r['recuperation_nb']} / {r['recuperation_montant']:,.2f}")
