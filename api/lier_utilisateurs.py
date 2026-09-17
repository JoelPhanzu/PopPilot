"""
Étape 1 (suite) — RELIER les comptes Supabase Auth à la table `utilisateur`.

POURQUOI ce script plutôt que de coller des UUID dans un .sql : les UUID changent
dès qu'un compte est supprimé/recréé dans Authentication > Users. Ici on les relit
dans auth.users à chaque exécution, donc la liaison se répare toute seule.

Seule la CORRESPONDANCE métier est écrite en dur ci-dessous (email -> rôle, agence).
C'est elle qui décide qui voit quoi : la modifier est une décision de gouvernance.

Idempotent : relançable sans risque (ON CONFLICT sur login).
Usage :  python lier_utilisateurs.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text                    # noqa: E402
from socle.schema import get_engine            # noqa: E402  (charge .env)

# email Supabase -> (login, nom complet, rôle, agence)
# Rôles valides (socle/auth.py) : DIRECTION, CDG, AGENCE, AUDIT.
# DIRECTION/CDG/AUDIT voient toutes les agences ; seuls DIRECTION/CDG importent.
CORRESPONDANCE = {
    "daf@poppilot.com":        ("daf",        "Directeur Administratif et Financier", "DIRECTION", None),
    "cdg@poppilot.com":        ("cdg",        "Contrôleur de gestion",                "CDG",       None),
    "bmvictoire@poppilot.com": ("bmvictoire", "Responsable agence Victoire",          "AGENCE",    "AGENCE DE VICTOIRE"),
    "audit@poppilot.com":      ("audit",      "Auditeur interne",                     "AUDIT",     None),
}

# mot_de_passe_hash / sel sont NOT NULL dans le schéma mais ne servent plus :
# l'authentification est entièrement déléguée à Supabase Auth.
NEUTRE = "supabase"


def main() -> int:
    moteur = get_engine()
    with moteur.begin() as c:
        comptes = {r.email: r.id for r in c.execute(text(
            "SELECT id, email FROM auth.users"))}

        introuvables = [e for e in CORRESPONDANCE if e not in comptes]
        if introuvables:
            print("[KO] comptes absents de Authentication > Users :")
            for e in introuvables:
                print("       -", e)
            print("     Les créer dans Supabase, puis relancer.")
            return 1

        for email, (login, nom, role, agence) in CORRESPONDANCE.items():
            c.execute(text("""
                INSERT INTO utilisateur (login, nom_complet, role, agence, actif,
                                         date_creation, mot_de_passe_hash, sel, auth_uid)
                VALUES (:login, :nom, :role, :agence, true, CURRENT_DATE,
                        :neutre, :neutre, :uid)
                ON CONFLICT (login) DO UPDATE
                   SET nom_complet = EXCLUDED.nom_complet,
                       role        = EXCLUDED.role,
                       agence      = EXCLUDED.agence,
                       actif       = true,
                       auth_uid    = EXCLUDED.auth_uid
            """), {"login": login, "nom": nom, "role": role, "agence": agence,
                   "neutre": NEUTRE, "uid": comptes[email]})
            print(f"[OK]   {login:11s} {role:10s} "
                  f"{(agence or '(toutes agences)'):22s} <- {email}")

        orphelins = c.execute(text(
            "SELECT login FROM utilisateur WHERE auth_uid IS NULL")).scalars().all()
        if orphelins:
            print(f"[ATTN] lignes sans compte Supabase (ne pourront pas se connecter) : "
                  f"{orphelins}")

    print("\nLiaison terminée. Contrôle : python verifier_supabase.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
