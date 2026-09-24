"""
PopPilot API — compte d'exploitation PAR AGENCE (chantier 3), en lecture.

  GET /compte-resultat-agence/arretes      mois disponibles (le plus récent d'abord)
  GET /compte-resultat-agence?arrete=…     postes × agences, tel qu'importé

Aucun calcul : les montants sont ceux du fichier du CDG (déjà contrôlé à l'import :
MICROPOP = Σ agences). Le total renvoyé est la somme des agences VISIBLES par l'appelant.

Ordre et nature des postes : ceux du fichier. Les lignes sont restituées dans leur ordre
d'insertion (celui du fichier) ; un poste avant « TOTAL PRODUITS » est un produit, entre
« TOTAL PRODUITS » et « TOTAL CHARGES » une charge.

CLOISONNEMENT : un rôle AGENCE ne reçoit que la colonne de son agence (le total est alors
le sien) ; il ne voit jamais les résultats des autres agences.
"""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select

from socle.schema import CompteResultatAgence as CRA, get_session

from auth_supabase import ROLES_ACCES_TOTAL, exiger_role, utilisateur_courant

routeur = APIRouter(tags=["compte-resultat-agence"])


def _d(s: str) -> dt.date:
    try:
        return dt.date.fromisoformat(s)
    except ValueError:
        raise HTTPException(422, f"Date invalide : {s} (format attendu AAAA-MM-JJ)")


def _nature(poste: str, etat: str) -> tuple[str, str]:
    """(nature de la ligne, état suivant). etat : 'produits' puis 'charges' puis 'fin'."""
    p = " ".join(poste.upper().split())
    if p.startswith("TOTAL PRODUITS"):
        return "total_produits", "charges"
    if p.startswith("TOTAL CHARGES"):
        return "total_charges", "fin"
    if "RESULTAT" in p and "COMPTABLE" in p:
        return "resultat", etat
    return ("produit" if etat == "produits" else "charge"), etat


@routeur.get("/compte-resultat-agence/arretes")
def endpoint_arretes(user: dict = Depends(utilisateur_courant)):
    exiger_role(user, ROLES_ACCES_TOTAL | {"AGENCE"})
    s = get_session()
    try:
        dates = s.execute(select(CRA.date_arrete).distinct()
                          .order_by(CRA.date_arrete.desc())).scalars().all()
    finally:
        s.close()
    return {"arretes": [d.isoformat() for d in dates]}


@routeur.get("/compte-resultat-agence")
def endpoint_compte_resultat(arrete: str = Query(..., description="AAAA-MM-JJ"),
                             user: dict = Depends(utilisateur_courant)):
    exiger_role(user, ROLES_ACCES_TOTAL | {"AGENCE"})
    date_arrete = _d(arrete)
    s = get_session()
    try:
        lignes = s.execute(select(CRA.poste, CRA.agence, CRA.montant)
                           .where(CRA.date_arrete == date_arrete).order_by(CRA.id)).all()
    finally:
        s.close()
    if not lignes:
        raise ValueError(f"Aucun compte de résultat par agence importé pour {arrete}.")

    agences = list(dict.fromkeys(ag for _p, ag, _m in lignes))
    if user["role"] not in ROLES_ACCES_TOTAL:
        sienne = (user.get("agence") or "").strip().upper()
        agences = [a for a in agences if a.strip().upper() == sienne]
        if not agences:
            raise HTTPException(403, "Votre agence ne figure pas dans ce compte de résultat.")

    postes: dict[str, dict] = {}
    for poste, agence, montant in lignes:
        if agence in agences:
            postes.setdefault(poste, {})[agence] = montant or 0.0

    etat, sortie = "produits", []
    for poste, montants in postes.items():
        nature, etat = _nature(poste, etat)
        sortie.append({"poste": poste, "nature": nature, "montants": montants,
                       "total": round(sum(montants.values()), 2)})
    return {"arrete": arrete, "role": user["role"], "agences": agences,
            "portee": "MICROPOP" if user["role"] in ROLES_ACCES_TOTAL else agences[0],
            "postes": sortie}
