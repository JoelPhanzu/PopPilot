"""
Couche d'historisation (Lot 0.3) — CLAUDE.md §16, §20, §23, §69.2.

Trois garanties :
1. Idempotence : ré-importer une date_arrete d'un domaine REMPLACE proprement (pas de doublon).
2. Résolution « snapshot le plus récent à la date T » — jamais d'interpolation silencieuse (§20.2).
3. date_arrete (comptable) distincte de date_snapshot (import) ; date_arrete fait foi (§69.2).
"""
from __future__ import annotations

import datetime as dt
from typing import Optional

from sqlalchemy import delete, select, func

from socle.schema import (
    FaitCredit, FaitRemboursementAttendu, FaitRemboursementRealise, FaitEpargne,
    FaitBalance, FaitGrandLivre, FaitTransactionCaisse, ImportLog, ParamCalendrierOuvre,
)

# domaine logique → table de faits
DOMAINES = {
    "credit": FaitCredit,
    "remboursement_attendu": FaitRemboursementAttendu,
    "remboursement_realise": FaitRemboursementRealise,
    "epargne": FaitEpargne,
    "balance": FaitBalance,
    "grand_livre": FaitGrandLivre,
    "transaction_caisse": FaitTransactionCaisse,
}


def purge_snapshot(session, domaine: str, date_arrete: dt.date, *, devise: str | None = None) -> int:
    """Supprime le snapshot existant (idempotence, règle I-4). Renvoie le nb de lignes purgées.

    `devise` restreint la purge à une seule devise. INDISPENSABLE pour la balance :
    un même arrêté porte la balance USD (bilan, indicateurs) ET la balance CDF (FINA).
    Purger sans distinguer la devise supprimait l'une en important l'autre, et le bilan
    « USD » se retrouvait alimenté par des montants CDF, sans erreur visible.
    """
    table = DOMAINES[domaine]
    conditions = [table.date_arrete == date_arrete]
    if devise is not None:
        conditions.append(table.devise == devise)
    n = session.execute(
        select(func.count()).select_from(table).where(*conditions)
    ).scalar_one()
    session.execute(delete(table).where(*conditions))
    return n


def enregistrer_import(session, *, domaine, fichier, date_snapshot, date_arrete,
                       acceptees, rejetees, message=""):
    session.add(ImportLog(
        domaine=domaine, fichier=fichier,
        date_snapshot=date_snapshot, date_arrete=date_arrete,
        lignes_acceptees=acceptees, lignes_rejetees=rejetees,
        horodatage=dt.datetime.now(), message=message,
    ))


def dates_arrete_disponibles(session, domaine: str) -> list[dt.date]:
    """Liste triée des date_arrete présentes pour un domaine."""
    table = DOMAINES[domaine]
    rows = session.execute(
        select(table.date_arrete).distinct().order_by(table.date_arrete)
    ).scalars().all()
    return list(rows)


def snapshot_le_plus_recent(session, domaine: str, date_cible: dt.date
                            ) -> tuple[Optional[dt.date], bool]:
    """Renvoie (date_arrete effective ≤ date_cible, exact?).
    exact=True si un snapshot existe pile à date_cible ; False s'il faut prendre l'antérieur.
    (None, False) si aucun snapshot antérieur. JAMAIS d'interpolation (§20.2)."""
    table = DOMAINES[domaine]
    d = session.execute(
        select(func.max(table.date_arrete)).where(table.date_arrete <= date_cible)
    ).scalar_one_or_none()
    if d is None:
        return None, False
    return d, (d == date_cible)


# ─── Calendrier ouvré (§69) — délégué au module socle.calendrier ──────────────
from socle import calendrier as _cal


def est_jour_ouvre(session, date: dt.date) -> bool:
    return _cal.est_jour_ouvre(session, date)


def dernier_jour_ouvre_du_mois(session, annee: int, mois: int) -> dt.date:
    return _cal.dernier_jour_ouvre_du_mois(session, annee, mois)


def jours_ouvres_ecoules(session, debut: dt.date, fin: dt.date) -> int:
    return _cal.jours_ouvres_ecoules(session, debut, fin)
