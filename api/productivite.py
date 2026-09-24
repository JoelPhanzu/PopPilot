"""
PopPilot API — productivité par agent / superviseur / agence (GET /productivite).

Enchaîne engine/productivite.py (qui s'appuie sur engine.par et la table des remboursements
importés). Les intérêts encaissés mesurent la PROFITABILITÉ ; ils n'entrent pas dans les primes.

CLOISONNEMENT : un rôle AGENCE ne reçoit que les lignes de son agence, et ses totaux sont la
somme de ces seules lignes (jamais l'institution).
"""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, Query

from engine.productivite import NIVEAUX, profil_productivite

from auth_supabase import ROLES_ACCES_TOTAL, exiger_role, utilisateur_courant

routeur = APIRouter(tags=["productivite"])


@routeur.get("/productivite")
def endpoint_productivite(arrete: str = Query(..., description="AAAA-MM-JJ"),
                          niveau: str = Query("agence", description="agent | superviseur | agence"),
                          user: dict = Depends(utilisateur_courant)):
    exiger_role(user, ROLES_ACCES_TOTAL | {"AGENCE"})
    if niveau not in NIVEAUX:
        raise HTTPException(422, f"niveau inconnu : {niveau} (attendu {', '.join(NIVEAUX)})")
    try:
        date_arrete = dt.date.fromisoformat(arrete)
    except ValueError:
        raise HTTPException(422, f"Date invalide : {arrete} (format attendu AAAA-MM-JJ)")

    r = profil_productivite(date_arrete, niveau)
    if user["role"] not in ROLES_ACCES_TOTAL:
        sienne = (user.get("agence") or "").strip().upper()
        if not sienne:
            raise HTTPException(403, "Profil AGENCE sans agence rattachée : aucune donnée visible.")
        r["lignes"] = [l for l in r["lignes"] if l["agence"].strip().upper() == sienne]
        r["totaux"] = {c: sum(l[c] for l in r["lignes"]) for c in r.get("totaux", {})}
    r["role"] = user["role"]
    return r
