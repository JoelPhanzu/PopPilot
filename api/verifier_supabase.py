"""
Étape 1 du guide — VÉRIFIER que Supabase est correctement monté.

Contrôle, dans l'ordre, ce que le guide demande de valider :
  1. api/.env est lisible et DATABASE_URL pointe bien sur Supabase.
  2. La connexion PostgreSQL s'établit.
  3. Les 30 tables de supabase/01_schema.sql sont là (01_schema.sql exécuté).
  4. La colonne utilisateur.auth_uid existe (02_auth_rls.sql exécuté).
  5. Les fonctions pp_role / pp_agence / pp_acces_total existent.
  6. RLS ACTIVÉ sur les tables cloisonnées, avec leurs policies.
  7. Le rôle de connexion est-il soumis au RLS, ou le contourne-t-il (BYPASSRLS) ?
  8. auth_uid est unique (sinon le rôle appliqué serait non déterministe).
  9. Les utilisateurs sont créés ET reliés à un compte Supabase (auth_uid non nul).

Ne modifie RIEN : lecture seule. Aucun mot de passe n'est affiché.

Usage :  python verifier_supabase.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text                       # noqa: E402
from socle.schema import (Base, get_engine, cible_base,          # noqa: E402
                          env_encore_gabarit)                    # (charge .env)

def tables_cloisonnees() -> list[str]:
    """Tables à cloisonner = celles qui portent une colonne `agence`, DÉRIVÉES du
    modèle (et non figées dans une liste).

    POURQUOI : une liste en dur vieillit en silence. Une 9e table de faits ajoutée
    au schéma ne serait jamais contrôlée et le script afficherait quand même tout
    vert — exactement le genre de trou qu'un vérificateur est censé fermer.

    `utilisateur` est exclue : sa colonne `agence` désigne l'agence DE RATTACHEMENT
    de la personne, pas l'agence propriétaire d'une donnée métier.
    """
    return sorted(n for n, t in Base.metadata.tables.items()
                  if "agence" in t.columns and n != "utilisateur")

OK, KO, ATTENTION = "[OK]   ", "[KO]   ", "[ATTN] "
_problemes: list[str] = []


def _dire(etat: str, message: str):
    print(etat + message)
    if etat == KO:
        _problemes.append(message)


def main() -> int:
    print("=" * 72)
    print("PopPilot — vérification de l'étape 1 (Supabase)")
    print("=" * 72)

    url = os.environ.get("DATABASE_URL")
    if not url:
        _dire(KO, "DATABASE_URL absente. Copier api/.env.example en api/.env et y coller "
                  "l'URL de connexion (Supabase > Project Settings > Database > URI).")
        return 1
    gabarit = env_encore_gabarit()
    if gabarit:
        _dire(KO, gabarit)
        print("\n  Ouvrir api/.env et remplacer les valeurs entre crochets par les vraies.")
        return 1
    _dire(OK, f"DATABASE_URL lue — cible : {cible_base()}")

    if "supabase" not in url and "postgres" not in url:
        _dire(ATTENTION, "l'URL ne ressemble pas à une base PostgreSQL/Supabase.")

    try:
        moteur = get_engine()
        with moteur.connect() as c:
            version = c.execute(text("SELECT version()")).scalar_one()
    except Exception as e:
        _dire(KO, f"connexion impossible : {type(e).__name__} — {e}")
        print("\n  Pistes : mot de passe de la base incorrect dans l'URL, projet Supabase "
              "en pause, ou réseau/pare-feu.")
        return 1
    _dire(OK, f"connexion établie — {version.split(',')[0]}")

    with moteur.connect() as c:
        # 3. tables
        presentes = {r[0] for r in c.execute(text(
            "SELECT table_name FROM information_schema.tables WHERE table_schema='public'"))}
        attendues = set(Base.metadata.tables)
        manquantes = attendues - presentes
        if manquantes:
            _dire(KO, f"{len(manquantes)} table(s) manquante(s) : {sorted(manquantes)}")
            print("       -> exécuter supabase/01_schema.sql dans l'éditeur SQL Supabase.")
        else:
            _dire(OK, f"{len(attendues)} tables présentes (01_schema.sql exécuté)")

        # 4. colonne auth_uid
        a_auth_uid = c.execute(text(
            "SELECT count(*) FROM information_schema.columns "
            "WHERE table_name='utilisateur' AND column_name='auth_uid'")).scalar_one()
        if a_auth_uid:
            _dire(OK, "utilisateur.auth_uid présente (lien vers auth.users)")
        else:
            _dire(KO, "utilisateur.auth_uid ABSENTE -> exécuter supabase/02_auth_rls.sql.")

        # 5. fonctions d'aide
        fonctions = {r[0] for r in c.execute(text(
            "SELECT proname FROM pg_proc WHERE proname IN "
            "('pp_role','pp_agence','pp_acces_total')"))}
        attendues_fn = {"pp_role", "pp_agence", "pp_acces_total"}
        if attendues_fn <= fonctions:
            _dire(OK, "fonctions pp_role / pp_agence / pp_acces_total présentes")
        else:
            _dire(KO, f"fonctions manquantes : {sorted(attendues_fn - fonctions)} "
                      "-> exécuter supabase/02_auth_rls.sql.")

        # 6. RLS + policies sur les tables cloisonnées
        cloisonnees = tables_cloisonnees()
        sans_rls, sans_policy = [], []
        for t in cloisonnees:
            if t not in presentes:
                continue
            actif = c.execute(text(
                "SELECT relrowsecurity FROM pg_class WHERE relname=:t"), {"t": t}).scalar()
            if not actif:
                sans_rls.append(t)
            nb = c.execute(text(
                "SELECT count(*) FROM pg_policies WHERE tablename=:t"), {"t": t}).scalar_one()
            if not nb:
                sans_policy.append(t)
        if sans_rls:
            _dire(KO, f"RLS DÉSACTIVÉ sur : {sans_rls} — le cloisonnement base ne protège rien.")
        elif not sans_policy:
            _dire(OK, f"RLS actif + policies sur les {len(cloisonnees)} tables cloisonnées "
                      f"(dérivées du modèle)")
        if sans_policy:
            _dire(KO, f"aucune policy sur : {sans_policy}")

        # 6 bis. le rôle de connexion contourne-t-il le RLS ?
        #        Déterminant : l'API se connecte avec CE rôle. S'il a BYPASSRLS, tout
        #        le travail de policies ci-dessus ne protège PAS les appels API — seul
        #        le filtre de api/auth_supabase.py les cloisonne. Sans cet avertissement,
        #        un [OK] "RLS actif" laisse croire à une protection qui n'opère pas ici.
        r = c.execute(text(
            "SELECT current_user AS u, "
            "COALESCE((SELECT rolbypassrls FROM pg_roles WHERE rolname = current_user), false) AS bypass, "
            "COALESCE((SELECT rolsuper FROM pg_roles WHERE rolname = current_user), false) AS super"
        )).one()
        if r.bypass or r.super:
            _dire(ATTENTION, f"connexion en '{r.u}' qui CONTOURNE le RLS "
                             f"(bypassrls={r.bypass}, superuser={r.super}) : les policies "
                             f"ne protègent pas ce canal.")
            print("         -> le cloisonnement des appels API repose alors ENTIÈREMENT sur")
            print("            le filtre de api/auth_supabase.py. Niveau 2 obligatoire.")
        else:
            _dire(OK, f"connexion en '{r.u}' : soumise au RLS")

        # 6 ter. unicité de auth_uid
        #        pp_role() fait SELECT ... LIMIT 1 sans ORDER BY : deux lignes partageant
        #        un auth_uid rendraient le rôle non déterministe (un AGENCE pourrait
        #        hériter d'un DIRECTION). Échec silencieux -> on le rend visible.
        if a_auth_uid:
            unique = c.execute(text(
                "SELECT count(*) FROM pg_constraint "
                "WHERE conrelid = 'utilisateur'::regclass AND contype = 'u' "
                "AND conkey = ARRAY[(SELECT attnum FROM pg_attribute "
                "WHERE attrelid = 'utilisateur'::regclass AND attname = 'auth_uid')]"
            )).scalar_one()
            doublons = c.execute(text(
                "SELECT count(*) FROM (SELECT auth_uid FROM utilisateur "
                "WHERE auth_uid IS NOT NULL GROUP BY auth_uid HAVING count(*) > 1) d"
            )).scalar_one()
            if doublons:
                _dire(KO, f"{doublons} auth_uid en DOUBLON : le rôle appliqué serait "
                          f"tiré au hasard entre les lignes concernées.")
            elif not unique:
                _dire(ATTENTION, "pas de contrainte UNIQUE sur utilisateur.auth_uid "
                                 "-> exécuter supabase/02_auth_rls.sql (version à jour).")
            else:
                _dire(OK, "auth_uid unique (rôle déterministe)")

        # 7. utilisateurs reliés à Supabase Auth
        if "utilisateur" in presentes and a_auth_uid:
            lignes = c.execute(text(
                "SELECT login, role, agence, auth_uid IS NOT NULL AS lie, actif "
                "FROM utilisateur ORDER BY login")).all()
            if not lignes:
                _dire(KO, "table utilisateur VIDE -> exécuter supabase/03_utilisateurs_test.sql "
                          "après avoir créé les comptes dans Authentication > Users.")
            else:
                non_lies = [l.login for l in lignes if not l.lie]
                for l in lignes:
                    marque = "lié" if l.lie else "NON LIÉ à auth.users"
                    print(f"         - {l.login:10s} {l.role:10s} "
                          f"{(l.agence or '(toutes agences)'):22s} {marque}"
                          f"{'' if l.actif else '  [INACTIF]'}")
                if non_lies:
                    _dire(KO, f"comptes sans auth_uid : {non_lies} — ils ne pourront pas "
                              "s'authentifier via l'API.")
                else:
                    _dire(OK, f"{len(lignes)} utilisateur(s), tous reliés à Supabase Auth")

    # jeton JWT côté API (étape 2)
    if os.environ.get("SUPABASE_JWT_SECRET"):
        _dire(OK, "SUPABASE_JWT_SECRET présent (l'API peut vérifier les jetons)")
    else:
        _dire(KO, "SUPABASE_JWT_SECRET absent dans api/.env — tous les endpoints "
                  "authentifiés renverront 500.")

    print("\n" + "=" * 72)
    if _problemes:
        print(f"ÉTAPE 1 INCOMPLÈTE — {len(_problemes)} point(s) à régler :")
        for p in _problemes:
            print(f"  - {p}")
        return 1
    print("ÉTAPE 1 VALIDÉE — Supabase est monté, relié, et cloisonné AU NIVEAU BASE.")
    print("Rappel : le cloisonnement des appels API est un SECOND niveau, assuré par")
    print("api/auth_supabase.py — le RLS seul ne le garantit pas (cf. rôle de connexion).")
    print("Suite : étape 2, lancer l'API (uvicorn main:app --reload) puis GET /sante.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
