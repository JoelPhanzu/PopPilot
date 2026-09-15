"""
Moteur PAR & portefeuille (Lot 1.3) — CLAUDE.md §7.1, §7.4, §15, Livrable 2 (CR-*).

Définitions maison EXACTES (confirmées §7.1) :
  PAR1  = Σ encours des prêts où jours_de_retard > 0
  PAR30 = Σ encours où jours_de_retard > 30
  PAR90 = Σ encours où jours_de_retard > 90
  %PARx = PARx / encours total du niveau
Numérateur = encours TOTAL du prêt délinquant (pas le capital en retard). Seuils STRICTS.

Décliné AGENT › SUPERVISEUR › AGENCE › GLOBAL. Les niveaux agrégés somment ; les % sont
recalculés au niveau (jamais sommés).
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from sqlalchemy import select

from socle.schema import FaitCredit, get_session


@dataclass
class LignePAR:
    designation: str
    niveau: str                 # GLOBAL / AGENCE / SUPERVISEUR / AGENT
    encours: float = 0.0
    par1: float = 0.0
    par30: float = 0.0
    par90: float = 0.0
    nb_credits: int = 0
    nb_clients: float = 0.0     # Σ (1/nb crédits du client) — déduplication (§15.2)

    @property
    def pct_par1(self): return self.par1 / self.encours if self.encours else 0.0
    @property
    def pct_par30(self): return self.par30 / self.encours if self.encours else 0.0
    @property
    def pct_par90(self): return self.par90 / self.encours if self.encours else 0.0


def _agrege(prets, designation, niveau) -> LignePAR:
    r = LignePAR(designation=designation, niveau=niveau)
    # nb clients pondéré : 1 / (nb de crédits du client) — §15.2 (colonne AK)
    from collections import Counter
    credits_par_client = Counter(p.numero_client for p in prets)
    for p in prets:
        enc = p.encours or 0.0
        jr = p.jours_de_retard or 0
        r.encours += enc
        if jr > 0:  r.par1 += enc
        if jr > 30: r.par30 += enc
        if jr > 90: r.par90 += enc
        r.nb_credits += 1
        r.nb_clients += 1.0 / credits_par_client[p.numero_client]
    return r


def calculer_par(date_arrete: dt.date, db_path="socle/micropop.db") -> dict:
    """Renvoie {'global': LignePAR, 'agences': [LignePAR...], 'superviseurs':..., 'agents':...}."""
    s = get_session(db_path)
    prets = s.execute(
        select(FaitCredit).where(FaitCredit.date_arrete == date_arrete)
    ).scalars().all()
    s.close()

    if not prets:
        raise ValueError(f"Aucun prêt pour l'arrêté {date_arrete}. Importer d'abord l'extraction.")

    resultat = {"global": _agrege(prets, "MICROPOP", "GLOBAL"), "agences": [],
                "superviseurs": [], "agents": []}

    def grouper(cle):
        d = {}
        for p in prets:
            d.setdefault(cle(p), []).append(p)
        return d

    for ag, lst in sorted(grouper(lambda p: p.agence or "(sans agence)").items()):
        resultat["agences"].append(_agrege(lst, ag, "AGENCE"))
    for sup, lst in sorted(grouper(lambda p: p.superviseur or "(sans superviseur)").items()):
        resultat["superviseurs"].append(_agrege(lst, sup, "SUPERVISEUR"))
    for (ag, agent), lst in sorted(grouper(lambda p: (p.agence, p.agent_credit)).items()):
        resultat["agents"].append(_agrege(lst, f"{agent} [{ag}]", "AGENT"))

    return resultat


if __name__ == "__main__":
    import sys
    arrete = dt.date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else dt.date(2026, 5, 31)
    res = calculer_par(arrete)
    g = res["global"]
    print(f"GLOBAL {g.designation}: encours={g.encours:,.2f} "
          f"PAR1={g.par1:,.2f} PAR30={g.par30:,.2f} PAR90={g.par90:,.2f} "
          f"%PAR30={g.pct_par30:.2%}")
    for a in res["agences"]:
        print(f"  {a.designation:26s} enc={a.encours:12,.0f} PAR30={a.par30:11,.0f} "
              f"%PAR30={a.pct_par30:6.2%}")
