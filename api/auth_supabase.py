"""
PopPilot API — Sécurité : vérifier le jeton Supabase de l'appelant et appliquer
le cloisonnement par agence AU NIVEAU DE L'API.

POURQUOI (écart 4) : l'API se connecte à PostgreSQL avec le compte 'postgres', qui
IGNORE le RLS de Supabase. Donc le RLS seul ne protège PAS les appels via l'API.
→ L'API doit, à chaque requête, lire le jeton JWT de l'utilisateur, en extraire son
  identité, retrouver son rôle et son agence, et FILTRER les résultats en conséquence.

Cloisonnement à DEUX niveaux (ceinture + bretelles) :
  1. RLS dans Supabase  → protège les accès directs à la base.
  2. Filtre dans l'API  → protège les appels via FastAPI (ce fichier).
"""
from __future__ import annotations
import os
from fastapi import Depends, HTTPException, Header
from sqlalchemy import select
from socle.schema import Utilisateur, get_session

ROLES_ACCES_TOTAL = {"DIRECTION", "CDG", "AUDIT"}


def _decoder_jwt_supabase(token: str) -> str:
    """Renvoie l'UID (sub) de l'utilisateur à partir de son jeton Supabase.
    Vérifie la signature avec le secret JWT du projet (SUPABASE_JWT_SECRET)."""
    import jwt  # PyJWT
    secret = os.environ.get("SUPABASE_JWT_SECRET")
    if not secret:
        raise HTTPException(500, "SUPABASE_JWT_SECRET non configuré côté API.")
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"], audience="authenticated")
    except Exception as e:
        raise HTTPException(401, f"Jeton invalide : {e}")
    uid = payload.get("sub")
    if not uid:
        raise HTTPException(401, "Jeton sans identifiant utilisateur.")
    return uid


def utilisateur_courant(authorization: str = Header(None)) -> dict:
    """Dépendance FastAPI : identifie l'appelant et renvoie son profil.
    Header attendu : Authorization: Bearer <jeton_supabase>.
    Renvoie {login, role, agence}. Lève 401 si non authentifié."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Authentification requise (Bearer token).")
    token = authorization.split(" ", 1)[1].strip()
    uid = _decoder_jwt_supabase(token)

    s = get_session()
    u = s.execute(select(Utilisateur).where(Utilisateur.auth_uid == uid,
                                            Utilisateur.actif == True)).scalar_one_or_none()  # noqa: E712
    s.close()
    if not u:
        raise HTTPException(403, "Utilisateur inconnu ou inactif.")
    return {"login": u.login, "role": u.role, "agence": u.agence}


def agences_autorisees(user: dict, toutes_agences: list[str]) -> list[str]:
    """Liste des agences que l'utilisateur a le droit de voir (filtre API)."""
    if user["role"] in ROLES_ACCES_TOTAL:
        return list(toutes_agences)
    if user["role"] == "AGENCE" and user["agence"]:
        return [user["agence"]]
    return []


def filtrer_par_agence(user: dict, resultat_par_agence: list[dict],
                       cle_agence: str = "agence") -> list[dict]:
    """Filtre une liste de résultats pour ne garder que les agences autorisées.
    Utilisé sur les endpoints qui renvoient un détail par agence (ex. /par)."""
    if user["role"] in ROLES_ACCES_TOTAL:
        return resultat_par_agence
    autorisees = set(agences_autorisees(user, [r[cle_agence] for r in resultat_par_agence]))
    return [r for r in resultat_par_agence if r.get(cle_agence) in autorisees]


def exiger_role(user: dict, roles: set[str]):
    """Bloque si l'utilisateur n'a pas un rôle autorisé (ex. import réservé DIRECTION/CDG)."""
    if user["role"] not in roles:
        raise HTTPException(403, f"Action réservée aux rôles : {', '.join(sorted(roles))}.")
