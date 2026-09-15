"""
Authentification et gestion des utilisateurs — CLAUDE.md (sécurité plateforme).
Login simple (mot de passe haché sha256 + sel). Rôles et cloisonnement par agence.

Rôles :
  - DIRECTION : accès total (tous domaines, toutes agences)
  - CDG       : accès total (contrôle de gestion)
  - AGENCE    : cloisonné à SON agence uniquement
  - AUDIT     : lecture seule, toutes agences
"""
from __future__ import annotations
import datetime as dt
import hashlib
import secrets
from sqlalchemy import select
from socle.schema import Utilisateur, get_session, init_db

ROLES = ["DIRECTION", "CDG", "AGENCE", "AUDIT"]
ROLES_ACCES_TOTAL = {"DIRECTION", "CDG", "AUDIT"}   # voient toutes les agences


def _hash(sel, mdp):
    return hashlib.sha256((sel + mdp).encode("utf-8")).hexdigest()


def creer_utilisateur(login, mot_de_passe, role, nom_complet="", agence=None,
                      db_path="socle/micropop.db"):
    assert role in ROLES, f"Rôle invalide : {role}"
    if role == "AGENCE" and not agence:
        raise ValueError("Un utilisateur AGENCE doit avoir une agence.")
    init_db(db_path)
    s = get_session(db_path)
    if s.execute(select(Utilisateur).where(Utilisateur.login == login)).scalar_one_or_none():
        s.close(); raise ValueError(f"Login déjà pris : {login}")
    sel = secrets.token_hex(8)
    s.add(Utilisateur(login=login, nom_complet=nom_complet, sel=sel,
                      mot_de_passe_hash=_hash(sel, mot_de_passe), role=role,
                      agence=agence, actif=True, date_creation=dt.date.today()))
    s.commit(); s.close()
    return {"login": login, "role": role, "agence": agence}


def verifier(login, mot_de_passe, db_path="socle/micropop.db"):
    """Renvoie l'utilisateur (dict) si login/mdp corrects et compte actif, sinon None."""
    s = get_session(db_path)
    u = s.execute(select(Utilisateur).where(Utilisateur.login == login)).scalar_one_or_none()
    if u and u.actif and u.mot_de_passe_hash == _hash(u.sel, mot_de_passe):
        u.derniere_connexion = dt.datetime.now()
        s.commit()
        res = {"login": u.login, "nom": u.nom_complet, "role": u.role, "agence": u.agence}
        s.close(); return res
    s.close(); return None


def agences_visibles(user, toutes_agences):
    """Liste des agences que l'utilisateur a le droit de voir."""
    if user["role"] in ROLES_ACCES_TOTAL:
        return list(toutes_agences)
    return [user["agence"]]      # AGENCE : uniquement la sienne


def peut_importer(user):
    """Seuls DIRECTION et CDG peuvent importer des données."""
    return user["role"] in {"DIRECTION", "CDG"}


def seed_utilisateurs(db_path="socle/micropop.db"):
    """Comptes de démonstration (à changer en production)."""
    init_db(db_path)
    comptes = [
        ("admin", "admin2026", "DIRECTION", "Directeur Général Adjoint", None),
        ("cdg", "cdg2026", "CDG", "Contrôleur de gestion", None),
        ("victoire", "agence2026", "AGENCE", "Responsable Victoire", "AGENCE DE VICTOIRE"),
        ("audit", "audit2026", "AUDIT", "Auditeur interne", None),
    ]
    created = []
    for login, mdp, role, nom, ag in comptes:
        try:
            creer_utilisateur(login, mdp, role, nom, ag, db_path)
            created.append(login)
        except ValueError:
            pass
    return created


if __name__ == "__main__":
    print("Comptes créés :", seed_utilisateurs())
    print("Test admin:", verifier("admin", "admin2026"))
    print("Test mauvais mdp:", verifier("admin", "xxx"))
    print("Test agence:", verifier("victoire", "agence2026"))
