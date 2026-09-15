"""
Calendrier ouvré RDC (§69) — flexible et dynamique.

Trois couches, de la plus générale à la plus spécifique (la plus spécifique gagne) :
  1. Règle hebdomadaire par défaut : dimanche NON ouvré, samedi ouvré.
  2. Fériés RÉCURRENTS RDC (dates fixes) — générés pour toute année.
  3. EXCEPTIONS saisies (table param_calendrier_ouvre) — priorité absolue :
     - report d'un férié tombant un week-end (arrêté ministériel) ;
     - jour non ouvré exceptionnel (deuil, salubrité…) ;
     - jour normalement chômé mais exceptionnellement travaillé.

Rien n'est figé en dur dans le code métier : la couche 3 permet de tout surcharger à la main.
"""
from __future__ import annotations

import datetime as dt
from sqlalchemy import select

from socle.schema import ParamCalendrierOuvre

# ── Couche 2 : fériés récurrents RDC (jour, mois) → libellé ────────────────────
FERIES_RECURRENTS = {
    (1, 1): "Nouvel An",
    (4, 1): "Journée des Martyrs de l'Indépendance",
    (16, 1): "Héros national Laurent-Désiré Kabila",
    (17, 1): "Héros national Patrice-Emery Lumumba",
    (6, 4): "Combat de Simon Kimbangu et de la conscience africaine",
    (1, 5): "Fête du Travail",
    (17, 5): "Journée de la Révolution et des Forces Armées",
    (30, 6): "Anniversaire de l'Indépendance",
    (1, 8): "Fête des Parents",
    (25, 12): "Noël",
}


def feries_de_lannee(annee: int) -> dict[dt.date, str]:
    """Fériés fixes récurrents pour une année (hors reports, qui sont des exceptions saisies)."""
    return {dt.date(annee, m, j): lib for (j, m), lib in FERIES_RECURRENTS.items()}


def est_ferie_recurrent(date: dt.date) -> bool:
    return (date.day, date.month) in FERIES_RECURRENTS


def est_jour_ouvre(session, date: dt.date) -> bool:
    """Vrai si le jour est travaillé. Ordre de priorité : exception saisie > férié récurrent >
    règle hebdomadaire (dimanche non ouvré)."""
    # Couche 3 — exception saisie : priorité absolue
    row = session.execute(
        select(ParamCalendrierOuvre).where(ParamCalendrierOuvre.date == date)
    ).scalar_one_or_none()
    if row is not None:
        return row.est_ouvre
    # Couche 2 — férié récurrent fixe
    if est_ferie_recurrent(date):
        return False
    # Couche 1 — règle hebdomadaire (dimanche non ouvré, samedi ouvré)
    return date.weekday() != 6


# ── Saisie des exceptions (l'« interface » côté données ; l'UI viendra en Phase 1+) ──
def declarer_exception(session, date: dt.date, est_ouvre: bool, libelle: str = ""):
    """Pointer/saisir un jour : férié reporté, non-ouvré exceptionnel, ou travaillé exceptionnel.
    Idempotent : re-déclarer une date met à jour."""
    row = session.execute(
        select(ParamCalendrierOuvre).where(ParamCalendrierOuvre.date == date)
    ).scalar_one_or_none()
    if row is None:
        session.add(ParamCalendrierOuvre(date=date, est_ouvre=est_ouvre, libelle=libelle))
    else:
        row.est_ouvre = est_ouvre
        row.libelle = libelle
    session.commit()


def reporter_ferie(session, date_ferie: dt.date, date_report: dt.date, libelle: str = ""):
    """Arrêté ministériel : un férié tombant un week-end est reporté (souvent au lundi).
    → le jour de report devient NON ouvré (chômé)."""
    lib = libelle or f"Report de {FERIES_RECURRENTS.get((date_ferie.day, date_ferie.month), 'férié')}"
    declarer_exception(session, date_report, est_ouvre=False, libelle=lib)


def suggerer_reports(session, annee: int) -> list[tuple[dt.date, str, str]]:
    """Aide à la saisie : liste les fériés récurrents tombant un dimanche (candidats au report).
    Ne décide RIEN — propose ; la validation est humaine (arrêté)."""
    out = []
    for d, lib in feries_de_lannee(annee).items():
        if d.weekday() == 6:  # dimanche
            lundi = d + dt.timedelta(days=1)
            out.append((d, lib, f"tombe un dimanche → report probable au lundi {lundi:%d/%m}"))
    return out


# ── Fonctions de période (identiques d'API à l'ancienne historisation) ─────────
def dernier_jour_ouvre_du_mois(session, annee: int, mois: int) -> dt.date:
    if mois == 12:
        prem_suivant = dt.date(annee + 1, 1, 1)
    else:
        prem_suivant = dt.date(annee, mois + 1, 1)
    d = prem_suivant - dt.timedelta(days=1)
    while not est_jour_ouvre(session, d):
        d -= dt.timedelta(days=1)
    return d


def jours_ouvres_ecoules(session, debut: dt.date, fin: dt.date) -> int:
    n, d = 0, debut
    while d <= fin:
        if est_jour_ouvre(session, d):
            n += 1
        d += dt.timedelta(days=1)
    return n
