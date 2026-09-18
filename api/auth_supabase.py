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

VÉRIFICATION DE LA SIGNATURE — deux régimes Supabase, tous deux gérés ici :
  - **Clés de signature asymétriques** (défaut des projets récents) : le jeton
    est signé en ES256 (clé ECC P-256) et se vérifie avec la clé PUBLIQUE du
    projet, publiée sur <SUPABASE_URL>/auth/v1/.well-known/jwks.json. Aucun
    secret à partager avec l'API : elle n'a besoin que de SUPABASE_URL.
  - **Secret partagé hérité** : jeton HS256, vérifié avec SUPABASE_JWT_SECRET.

Ne jamais figer `algorithms=["HS256"]` : un projet migré vers les clés de
signature émet des jetons ES256, que PyJWT rejette alors avec « The specified
alg value is not allowed » — message qui donne l'air d'un jeton corrompu alors
que c'est l'API qui regarde au mauvais endroit.
"""
from __future__ import annotations
import functools
import os
from urllib.parse import urlsplit
from fastapi import Depends, HTTPException, Header
from sqlalchemy import select
from socle.schema import Utilisateur, get_session

ROLES_ACCES_TOTAL = {"DIRECTION", "CDG", "AUDIT"}

# Rôles autorisés à ÉCRIRE dans le socle (import des fichiers du CBS).
# L'AUDIT a un accès total en LECTURE ; cela ne lui donne pas le droit d'alimenter la
# base. Confondre les deux ensembles ouvrirait l'import à un rôle de contrôle, qui doit
# précisément rester extérieur à ce qu'il contrôle.
# Miroir exact de ROLES_ECRITURE dans web/src/lib/roles.ts.
ROLES_ECRITURE = {"DIRECTION", "CDG"}

# Algorithmes à clé PUBLIQUE, utilisés par Supabase depuis les « JWT signing keys »
# (clé ECC P-256 → ES256 par défaut sur les projets récents).
ALGOS_ASYMETRIQUES = {"ES256", "ES384", "ES512",
                      "RS256", "RS384", "RS512",
                      "PS256", "PS384", "PS512", "EdDSA"}


def url_supabase() -> str | None:
    """Origine du projet Supabase (SUPABASE_URL), sans chemin ni slash final.

    Même précaution que côté front : on ne garde que le schéma et l'hôte. Une
    valeur copiée avec /rest/v1 construirait une URL de JWKS inexistante.
    """
    brut = (os.environ.get("SUPABASE_URL") or "").strip().strip('"').strip("'")
    if not brut.startswith(("http://", "https://")):
        return None
    morceaux = urlsplit(brut)
    if not morceaux.netloc:
        return None
    return f"{morceaux.scheme}://{morceaux.netloc}"


@functools.lru_cache(maxsize=4)
def _client_jwks(url_jwks: str):
    """Client JWKS mis en cache.

    Il garde les clés publiques en mémoire : sans ce cache, CHAQUE requête à
    l'API irait rechercher le JWKS chez Supabase — un aller-retour réseau par
    appel, et une API à genoux dès que Supabase ralentit.
    """
    import jwt  # PyJWT
    return jwt.PyJWKClient(url_jwks, cache_keys=True, lifespan=600)


def _cle_de_verification(token: str, alg: str):
    """Clé et algorithmes autorisés pour CE jeton, selon sa signature.

    Deux régimes coexistent chez Supabase :
      - **clés de signature asymétriques** (défaut des projets récents) : le
        jeton est signé ES256/RS256 et se vérifie avec la clé PUBLIQUE publiée
        au JWKS du projet. Il n'existe alors AUCUN secret partagé à configurer.
      - **secret partagé hérité** : jeton HS256, vérifié avec SUPABASE_JWT_SECRET.

    L'algorithme du jeton choisit le régime, mais ne peut pas faire glisser
    l'un vers l'autre : un jeton HS256 est toujours vérifié avec le SECRET du
    projet, jamais avec une clé publique. C'est ce qui ferme l'attaque classique
    de confusion d'algorithme, où l'on resigne un jeton en HS256 en se servant
    de la clé publique (connue de tous) comme secret.
    """
    if alg in ALGOS_ASYMETRIQUES:
        origine = url_supabase()
        if not origine:
            raise HTTPException(
                500,
                f"Ce jeton est signé en {alg} (clés de signature Supabase), mais "
                "SUPABASE_URL n'est pas configurée côté API : impossible d'aller "
                "chercher les clés publiques du projet. Ajouter dans api/.env : "
                "SUPABASE_URL=https://<ref>.supabase.co",
            )
        try:
            jwks = _client_jwks(f"{origine}/auth/v1/.well-known/jwks.json")
            return jwks.get_signing_key_from_jwt(token).key, [alg]
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(401, f"Clé publique introuvable pour ce jeton : {e}")

    if alg == "HS256":
        secret = os.environ.get("SUPABASE_JWT_SECRET")
        if not secret:
            raise HTTPException(
                500,
                "Jeton HS256 (secret partagé hérité) mais SUPABASE_JWT_SECRET "
                "n'est pas configuré côté API.",
            )
        return secret, ["HS256"]

    # « none » et compagnie : on refuse explicitement plutôt que de tenter.
    raise HTTPException(401, f"Algorithme de signature non accepté : {alg!r}.")


def _decoder_jwt_supabase(token: str) -> str:
    """Renvoie l'UID (sub) de l'utilisateur à partir de son jeton Supabase.

    La signature est TOUJOURS vérifiée, et uniquement avec l'algorithme annoncé
    par le jeton parmi ceux que l'on accepte — jamais une liste ouverte.
    """
    import jwt  # PyJWT
    try:
        entete = jwt.get_unverified_header(token)
    except Exception as e:
        raise HTTPException(401, f"Jeton illisible : {e}")

    alg = entete.get("alg") or ""
    cle, algos = _cle_de_verification(token, alg)

    # L'émetteur n'est vérifié que si on le connaît : les tests forgent des
    # jetons sans `iss`, et un déploiement réel, lui, renseigne SUPABASE_URL.
    origine = url_supabase()
    options = {"audience": "authenticated"}
    if origine:
        options["issuer"] = f"{origine}/auth/v1"

    try:
        payload = jwt.decode(token, cle, algorithms=algos, **options)
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Session expirée : reconnectez-vous.")
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
