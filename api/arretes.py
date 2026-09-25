"""
PopPilot API — arrêtés ENREGISTRÉS par domaine (règle du calendrier).

  GET /arretes/{domaine}      dates d'arrêté chargées, la plus récente d'abord

Règle d'affichage (CDG, 25/09/2026) : l'utilisateur choisit N'IMPORTE QUELLE date dans le
calendrier ; l'écran montre le DERNIER arrêté enregistré à cette date (arrêté ≤ date choisie),
et affiche cette date-là. Si la date précède tout import, le plus ancien arrêté enregistré.
Ex. : 5 juillet → chiffres ET date du 30 juin ; 30 juin → 30 juin.

La résolution se fait dans l'écran (web/src/lib/arretes.ts) à partir de cette liste ; ce module
ne fait que dire ce que la base contient vraiment (date_arrete fait foi, jamais date_snapshot).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from socle.schema import (CompteResultatAgence, FaitBalance, FaitCredit, FaitEpargne,
                          get_session)

from auth_supabase import utilisateur_courant

routeur = APIRouter(tags=["arretes"])

# domaine → table dont les arrêtés gouvernent l'écran
DOMAINES = {
    "credit": FaitCredit,                       # crédit, productivité, primes
    "balance": FaitBalance,                     # comptabilité, indicateurs, budget
    "epargne": FaitEpargne,
    "compte_resultat_agence": CompteResultatAgence,
}


def arretes_enregistres(domaine: str, db_path=None) -> list:
    table = DOMAINES[domaine]
    s = get_session(db_path) if db_path else get_session()   # défaut = base de l'API
    try:
        return s.execute(select(table.date_arrete).distinct()
                         .order_by(table.date_arrete.desc())).scalars().all()
    finally:
        s.close()


@routeur.get("/arretes/{domaine}")
def endpoint_arretes(domaine: str, user: dict = Depends(utilisateur_courant)):
    if domaine not in DOMAINES:
        raise HTTPException(422, f"domaine inconnu : {domaine} (attendu {', '.join(DOMAINES)})")
    # Des dates seulement, aucun montant : visibles par tout profil connecté.
    return {"domaine": domaine, "arretes": [d.isoformat() for d in arretes_enregistres(domaine)]}
