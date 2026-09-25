"""
PopPilot API — tableau de bord ÉPARGNE (engine/tableau_de_bord_epargne.py).

  GET /epargne/tableau-de-bord   stocks à l'arrêté, flux (dépôts / retraits) sur [début ; fin],
                                 M-1, couverture épargne / crédit, par agence / produit / type / client
  GET /epargne/top               Top N épargnants (solde USD, tous comptes du client)

STRICTEMENT ADDITIF : GET /epargne (synthèse validée) reste tel quel ; sans filtre, l'encours de
ce tableau de bord lui est égal au centime (tests/test_epargne.py).

CLOISONNEMENT : un rôle AGENCE est ramené à son agence (une autre demandée → 403) ; son total
est celui de sa seule agence, jamais l'agrégat MICROPOP.
"""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, Query

from auth_supabase import utilisateur_courant
from filtres_credit import _agence_imposee, _d

routeur = APIRouter(tags=["epargne"])

# Base visée : celle de la plateforme (Supabase si DATABASE_URL). Les tests la remplacent.
from socle.schema import BASE_PAR_DEFAUT  # noqa: E402
BASE = BASE_PAR_DEFAUT


def _filtres(user, agence, devise, type_depot, sexe, groupe, statut=None) -> dict:
    if devise and devise.upper() not in ("USD", "CDF"):
        raise HTTPException(422, f"devise inconnue : {devise} (attendu USD ou CDF)")
    if type_depot and type_depot not in ("a_vue", "a_terme", "obligatoire"):
        raise HTTPException(422, f"type_depot inconnu : {type_depot} (a_vue, a_terme, obligatoire)")
    if sexe and sexe.upper() not in ("H", "F", "PM"):
        raise HTTPException(422, f"sexe inconnu : {sexe} (attendu H, F ou PM)")
    if groupe and groupe not in ("oui", "non"):
        raise HTTPException(422, f"groupe : attendu oui ou non, reçu {groupe}")
    if statut and statut not in ("pp", "pm", "groupe"):
        raise HTTPException(422, f"statut inconnu : {statut} (attendu pp, pm ou groupe)")
    return {"agence": _agence_imposee(user, agence), "devise": devise, "type_depot": type_depot,
            "sexe": sexe, "groupe": groupe, "statut": statut}


@routeur.get("/epargne/tableau-de-bord")
def endpoint_tableau_de_bord_epargne(
        arrete: str | None = Query(None, description="Date de VALORISATION (défaut : dernier inventaire)"),
        debut: str | None = Query(None, description="Début de la période de FLUX (mois entiers)"),
        fin: str | None = Query(None, description="Fin de la période de FLUX"),
        niveau: str = Query("agence", description="agence | produit | type | client"),
        limite: int = Query(300, ge=1, le=10000),
        agence: str | None = None, devise: str | None = None, type_depot: str | None = None,
        sexe: str | None = None, groupe: str | None = None,
        statut: str | None = None,             # pp | pm | groupe (statut juridique du titulaire)
        user: dict = Depends(utilisateur_courant)):
    from engine.tableau_de_bord_epargne import NIVEAUX, tableau_de_bord_epargne
    if niveau not in NIVEAUX:
        raise HTTPException(422, f"niveau inconnu : {niveau} (attendu {', '.join(NIVEAUX)})")
    f = _filtres(user, agence, devise, type_depot, sexe, groupe, statut)
    if not arrete:
        from sqlalchemy import func, select
        from socle.schema import FaitEpargne, get_session
        s = get_session(BASE)
        try:
            dernier = s.execute(select(func.max(FaitEpargne.date_arrete))).scalar()
        finally:
            s.close()
        if dernier is None:
            raise HTTPException(404, "Aucun inventaire épargne importé.")
        arrete = dernier.isoformat()
    r = tableau_de_bord_epargne(_d(arrete), _d(debut) if debut else None, _d(fin) if fin else None,
                                niveau, f, db_path=BASE, limite=limite)
    r["role"] = user["role"]
    return r


@routeur.get("/epargne/top")
def endpoint_top_epargnants(
        arrete: str = Query(..., description="Date de valorisation AAAA-MM-JJ"),
        n: int = Query(10, ge=1, le=500),
        agence: str | None = None, devise: str | None = None, type_depot: str | None = None,
        sexe: str | None = None, groupe: str | None = None, statut: str | None = None,
        user: dict = Depends(utilisateur_courant)):
    from engine.tableau_de_bord_epargne import top_epargnants
    f = _filtres(user, agence, devise, type_depot, sexe, groupe, statut)
    return {"arrete": arrete, "n": n,
            "clients": top_epargnants(_d(arrete), n, f, db_path=BASE)}
