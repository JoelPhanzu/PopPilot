"""
Potentiel de fin de mois — « si rien ne change » (définitions CDG du 25/09/2026).

  - POTENTIEL COÛT DU RISQUE : le coût du risque qu'on constatera au dernier jour du mois si
    AUCUN remboursement n'arrive d'ici là. Les retards vieillissent (jours de retard + jours
    restants), certains prêts changent de tranche, et la provision suit.
  - POTENTIEL MIGRATION : les crédits SAINS aujourd'hui (retard 0) dont une échéance tombe
    avant la fin du mois : impayée, elle les fait entrer en PAR.

Aucune règle nouvelle : on PROJETTE les prêts à la fin du mois, puis on applique le moteur
validé engine.migrations.migrations_sur (coût du risque prêt par prêt vs M-1, barème daté).
Arrêté = dernier jour du mois → rien ne vieillit : le potentiel égale le réalisé.

Échéances : le CBS ne donne pas la prochaine échéance ; on la déduit de la date de
déboursement et de la fréquence (« Mensuelle » : même quantième chaque mois ; « Tous les
28 jours » : pas de 28 jours), bornée par la date de fin d'échéance.
"""
from __future__ import annotations

import calendar
import datetime as dt
from types import SimpleNamespace

from engine.migrations import migrations_sur


def fin_de_mois(d: dt.date) -> dt.date:
    return d.replace(day=calendar.monthrange(d.year, d.month)[1])


def _plus_mois(d: dt.date, n: int) -> dt.date:
    a, m = divmod(d.month - 1 + n, 12)
    annee, mois = d.year + a, m + 1
    return dt.date(annee, mois, min(d.day, calendar.monthrange(annee, mois)[1]))


def premiere_echeance_entre(p, apres: dt.date, jusqua: dt.date) -> dt.date | None:
    """Première échéance du prêt dans ]apres ; jusqua[ (une échéance le dernier jour n'est pas
    encore en retard ce jour-là). None si aucune ou fréquence inconnue."""
    dd = p.date_deboursement
    if dd is None:
        return None
    freq = (p.frequence or "").lower()
    fin = p.date_fin_echeance
    if "28" in freq:
        pas = 28
        k = max(1, (apres - dd).days // pas + 1)
        ech = dd + dt.timedelta(days=pas * k)
    elif "mens" in freq:
        k = max(1, (apres.year - dd.year) * 12 + apres.month - dd.month)
        ech = _plus_mois(dd, k)
        while ech <= apres:
            k += 1
            ech = _plus_mois(dd, k)
    else:
        return None
    if ech >= jusqua or (fin and ech > fin):
        return None
    return ech


def projeter(prets, arrete: dt.date, fin: dt.date | None = None) -> dict:
    """{numero_dossier: prêt projeté à `fin`} — mêmes champs que le moteur de migrations lit."""
    fin = fin or fin_de_mois(arrete)
    ecart = max(0, (fin - arrete).days)
    projetes = {}
    for p in prets:
        jr = p.jours_de_retard or 0
        if jr > 0:
            jr += ecart                          # aucun recouvrement : le retard vieillit
        else:
            ech = premiere_echeance_entre(p, arrete, fin)
            jr = (fin - ech).days if ech else 0  # échéance impayée → entrée en PAR
        projetes[p.numero_dossier] = SimpleNamespace(
            numero_dossier=p.numero_dossier, encours=p.encours, jours_de_retard=jr)
    return projetes


def potentiel_fin_de_mois(prets, prev_index: dict, bareme, arrete: dt.date) -> dict:
    """prets : sélection à l'arrêté ; prev_index : index COMPLET de l'arrêté M-1 (comme pour le
    coût du risque réalisé)."""
    fin = fin_de_mois(arrete)
    projetes = projeter(prets, arrete, fin)
    m = migrations_sur(projetes, prev_index, bareme) if prev_index else None
    sains = [p for p in prets if (p.jours_de_retard or 0) == 0]
    entrants = [p for p in sains if projetes[p.numero_dossier].jours_de_retard > 0]
    return {
        "date_projection": fin.isoformat(),
        "potentiel_cout_du_risque": m["cout_du_risque"] if m else None,
        "potentiel_migration_vers": m["migration_vers"] if m else None,
        "potentiel_migration_nb": len(entrants),
        "potentiel_migration_montant": sum(p.encours or 0.0 for p in entrants),
    }
