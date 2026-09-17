"""
Tests de sécurité de l'API — cloisonnement par agence AU NIVEAU DE L'API (écart 4).

POURQUOI CE TEST EXISTE : le RLS de Supabase ne protège QUE les accès directs à la base.
L'API, elle, se connecte en 'postgres' et IGNORE le RLS. Si le filtre de api/auth_supabase.py
disparaît ou se casse, un utilisateur AGENCE verrait les données de TOUTES les agences,
sans le moindre message d'erreur. Ce test est le garde-fou de ce deuxième niveau.

Il ne nécessite NI Supabase NI données réelles : base SQLite temporaire + jetons JWT forgés
avec un secret de test. Il valide la chaîne complète : jeton → identité → rôle → filtrage.

Lancer :  python tests/test_securite_api.py
"""
import datetime as dt
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import donnees_test as D   # compte rendu honnete (PASSE / SAUTE / ECHEC)

SECRET_TEST = "secret-jwt-de-test-uniquement-pour-les-tests-locaux"
DB = "socle/test_securite.db"

AGENCE_TESTEE = "AGENCE DE VICTOIRE"
AUTRES_AGENCES = ["AGENCE DE GOMA", "AGENCE DE MATADI"]


def _preparer():
    """Base de test + deux utilisateurs liés à un compte Supabase (auth_uid)."""
    # L'import de socle.schema charge api/.env (load_dotenv). Le nettoyage de
    # l'environnement doit donc venir APRES, sinon le premier test de la série
    # se fait re-remplir ses variables par le .env réel — et lui seul échoue,
    # les suivants profitant du module déjà importé. Piège vicieux : le test
    # semble alors dépendre de son rang dans la liste.
    from socle.schema import init_db, get_session, fermer_moteurs, Utilisateur

    os.environ["SUPABASE_JWT_SECRET"] = SECRET_TEST
    os.environ.pop("DATABASE_URL", None)        # forcer le repli SQLite local
    # Neutraliser la config réelle : ces cas testent le régime HS256 (secret
    # partagé) ; SUPABASE_URL activerait en plus la vérification de l'émetteur,
    # que les jetons forgés ici ne portent pas. Les cas ES256 la reposent.
    os.environ.pop("SUPABASE_URL", None)

    fermer_moteurs()                   # liberer le fichier SQLite (verrou Windows)
    if os.path.exists(DB):
        os.remove(DB)
    init_db(DB)

    uids = {"victoire": str(uuid.uuid4()), "cdg": str(uuid.uuid4())}
    s = get_session(DB)
    s.add_all([
        Utilisateur(login="victoire", nom_complet="Responsable Victoire",
                    mot_de_passe_hash="supabase", sel="supabase",
                    role="AGENCE", agence=AGENCE_TESTEE, actif=True,
                    date_creation=dt.date.today(), auth_uid=uids["victoire"]),
        Utilisateur(login="cdg", nom_complet="Contrôleur de gestion",
                    mot_de_passe_hash="supabase", sel="supabase",
                    role="CDG", agence=None, actif=True,
                    date_creation=dt.date.today(), auth_uid=uids["cdg"]),
    ])
    s.commit()
    s.close()

    # Router auth_supabase vers la base de test (il n'a pas de paramètre de chemin).
    import auth_supabase as A
    origine = A.get_session
    A.get_session = lambda *a, **k: origine(DB)
    return A, uids


def _jeton(uid: str, secret: str = SECRET_TEST) -> str:
    import jwt
    return jwt.encode({"sub": uid, "aud": "authenticated", "role": "authenticated",
                       "exp": int(dt.datetime.now().timestamp()) + 3600},
                      secret, algorithm="HS256")


def _jeton_es256(uid: str, cle_privee, origine: str) -> str:
    """Jeton signé comme le fait Supabase depuis les « JWT signing keys » : ES256."""
    import jwt
    return jwt.encode(
        {"sub": uid, "aud": "authenticated", "role": "authenticated",
         "iss": f"{origine}/auth/v1",
         "exp": int(dt.datetime.now().timestamp()) + 3600},
        cle_privee, algorithm="ES256")


def _brancher_jwks(A, cle_publique):
    """Remplace le client JWKS par la clé publique locale (aucun appel réseau)."""
    class _CleFactice:
        key = cle_publique

    class _ClientFactice:
        def get_signing_key_from_jwt(self, _token):
            return _CleFactice()

    A._client_jwks.cache_clear()
    origine_fn = A._client_jwks
    A._client_jwks = lambda *a, **k: _ClientFactice()
    return origine_fn


def _nettoyer():
    from socle.schema import fermer_moteurs
    fermer_moteurs()                             # libérer le fichier SQLite (Windows)
    if os.path.exists(DB):
        try:
            os.remove(DB)
        except PermissionError:
            pass


def test_jeton_resout_le_bon_profil():
    """Le jeton Supabase doit résoudre l'utilisateur via auth_uid (rôle + agence)."""
    A, uids = _preparer()
    u = A.utilisateur_courant(f"Bearer {_jeton(uids['victoire'])}")
    assert u["login"] == "victoire"
    assert u["role"] == "AGENCE"
    assert u["agence"] == AGENCE_TESTEE

    c = A.utilisateur_courant(f"Bearer {_jeton(uids['cdg'])}")
    assert c["role"] == "CDG" and c["agence"] is None
    _nettoyer()


def test_agence_ne_voit_que_son_agence():
    """LE test : un rôle AGENCE ne doit JAMAIS voir les lignes d'une autre agence."""
    A, uids = _preparer()
    u = A.utilisateur_courant(f"Bearer {_jeton(uids['victoire'])}")

    resultat = [{"agence": AGENCE_TESTEE, "encours": 100.0}] + \
               [{"agence": a, "encours": 200.0} for a in AUTRES_AGENCES]

    vu = A.filtrer_par_agence(u, resultat)
    assert [r["agence"] for r in vu] == [AGENCE_TESTEE], \
        f"FUITE : l'agence voit {[r['agence'] for r in vu]}"

    # le CDG, lui, voit tout
    cdg = A.utilisateur_courant(f"Bearer {_jeton(uids['cdg'])}")
    assert len(A.filtrer_par_agence(cdg, resultat)) == len(resultat)
    _nettoyer()


def test_endpoints_globaux_refuses_a_une_agence():
    """Compta, indicateurs, épargne = agrégats globaux : interdits à un rôle AGENCE."""
    from fastapi import HTTPException
    A, uids = _preparer()
    u = A.utilisateur_courant(f"Bearer {_jeton(uids['victoire'])}")
    try:
        A.exiger_role(u, A.ROLES_ACCES_TOTAL)
        raise AssertionError("FUITE : un rôle AGENCE a franchi exiger_role")
    except HTTPException as e:
        assert e.status_code == 403
    _nettoyer()


def test_jeton_contrefait_rejete():
    """Un jeton signé avec un autre secret doit être refusé (401), pas accepté."""
    from fastapi import HTTPException
    A, uids = _preparer()
    contrefait = _jeton(uids["cdg"], secret="secret-de-lattaquant-pas-celui-de-supabase")
    try:
        A.utilisateur_courant(f"Bearer {contrefait}")
        raise AssertionError("FAILLE : jeton contrefait accepté")
    except HTTPException as e:
        assert e.status_code == 401
    _nettoyer()


def test_sans_jeton_refuse():
    """Pas d'Authorization → 401. Aucun endpoint n'est ouvert."""
    from fastapi import HTTPException
    A, _ = _preparer()
    for entete in (None, "", "Basic abc", "Bearer"):
        try:
            A.utilisateur_courant(entete)
            raise AssertionError(f"FAILLE : en-tête {entete!r} accepté")
        except HTTPException as e:
            assert e.status_code == 401
    _nettoyer()


def test_endpoint_decaissements_ne_fuite_pas_le_global():
    """Un rôle AGENCE ne doit voir NI le détail NI le TOTAL des autres agences.

    Le défaut corrigé : `/decaissements` filtrait bien `par_agence`, mais renvoyait le
    bloc `global` de toute l'institution. Les tests précédents ne testaient que les
    fonctions d'aide (filtrer_par_agence), jamais les endpoints — la fuite passait donc
    au travers. Ce test appelle l'endpoint lui-même.
    """
    from socle.schema import get_session, FaitCredit
    A, uids = _preparer()
    arrete = dt.date(2026, 5, 30)

    s = get_session(DB)
    s.add_all([
        FaitCredit(date_arrete=arrete, date_snapshot=arrete, numero_dossier="D-VIC",
                   agence=AGENCE_TESTEE, montant_debourse=100.0,
                   date_deboursement=dt.date(2026, 5, 10), encours=100.0),
        FaitCredit(date_arrete=arrete, date_snapshot=arrete, numero_dossier="D-GOM",
                   agence="AGENCE DE GOMA", montant_debourse=900.0,
                   date_deboursement=dt.date(2026, 5, 11), encours=900.0),
    ])
    s.commit()
    s.close()

    import main as M
    origine = M.decaissements
    M.decaissements = lambda a, d, f: origine(a, d, f, db_path=DB)
    try:
        agence = A.utilisateur_courant(f"Bearer {_jeton(uids['victoire'])}")
        r = M.endpoint_decaissements(arrete="2026-05-30", debut="2026-05-01",
                                     fin="2026-05-31", user=agence)
        assert list(r["par_agence"]) == [AGENCE_TESTEE], r["par_agence"]
        assert r["global"]["volume"] == 100.0, \
            f"FUITE : l'agence lit le volume global {r['global']['volume']} (attendu 100)"
        assert r["global"]["nombre"] == 1
        assert r["portee"] == AGENCE_TESTEE

        cdg = A.utilisateur_courant(f"Bearer {_jeton(uids['cdg'])}")
        rc = M.endpoint_decaissements(arrete="2026-05-30", debut="2026-05-01",
                                      fin="2026-05-31", user=cdg)
        assert rc["global"]["volume"] == 1000.0, rc["global"]
        assert len(rc["par_agence"]) == 2
    finally:
        M.decaissements = origine
    _nettoyer()


def test_utilisateur_inactif_refuse():
    """Un compte désactivé ne doit plus rien pouvoir lire (403), même avec un jeton valide."""
    from fastapi import HTTPException
    from socle.schema import get_session, Utilisateur
    from sqlalchemy import select
    A, uids = _preparer()

    s = get_session(DB)
    u = s.execute(select(Utilisateur).where(Utilisateur.login == "victoire")).scalar_one()
    u.actif = False
    s.commit()
    s.close()

    try:
        A.utilisateur_courant(f"Bearer {_jeton(uids['victoire'])}")
        raise AssertionError("FAILLE : utilisateur désactivé accepté")
    except HTTPException as e:
        assert e.status_code == 403
    _nettoyer()


def test_jeton_es256_accepte():
    """Un jeton signé ES256 (clés de signature Supabase) doit être ACCEPTÉ.

    Le défaut corrigé : `jwt.decode(..., algorithms=["HS256"])` rejetait tout
    jeton d'un projet migré vers les clés de signature asymétriques, avec
    « The specified alg value is not allowed ». Le tableau de bord ne voyait
    qu'une erreur d'API, sans rapport apparent avec la configuration.
    """
    try:
        from cryptography.hazmat.primitives.asymmetric import ec
    except ImportError as e:                                     # pragma: no cover
        raise D.TestSaute(f"paquet `cryptography` absent : {e}")

    origine = "https://projet-de-test.supabase.co"
    A, uids = _preparer()
    ancien = _brancher_jwks(A, None)
    try:
        privee = ec.generate_private_key(ec.SECP256R1())
        A._client_jwks = lambda *a, **k: type(
            "C", (), {"get_signing_key_from_jwt":
                      lambda _s, _t: type("K", (), {"key": privee.public_key()})()})()
        os.environ["SUPABASE_URL"] = origine

        u = A.utilisateur_courant(f"Bearer {_jeton_es256(uids['victoire'], privee, origine)}")
        assert u["login"] == "victoire" and u["role"] == "AGENCE", \
            f"jeton ES256 mal resolu : {u}"
    finally:
        A._client_jwks = ancien
        A._client_jwks.cache_clear()
        os.environ.pop("SUPABASE_URL", None)
        _nettoyer()


def test_jeton_es256_contrefait_rejete():
    """Un jeton ES256 signé par UNE AUTRE clé doit être refusé (401).

    Vérifie que la clé publique sert bien à valider la signature, et qu'on ne
    se contente pas de lire le contenu du jeton.
    """
    try:
        from cryptography.hazmat.primitives.asymmetric import ec
    except ImportError as e:                                     # pragma: no cover
        raise D.TestSaute(f"paquet `cryptography` absent : {e}")

    from fastapi import HTTPException
    origine = "https://projet-de-test.supabase.co"
    A, uids = _preparer()
    ancien = _brancher_jwks(A, None)
    try:
        legitime = ec.generate_private_key(ec.SECP256R1())
        attaquant = ec.generate_private_key(ec.SECP256R1())
        A._client_jwks = lambda *a, **k: type(
            "C", (), {"get_signing_key_from_jwt":
                      lambda _s, _t: type("K", (), {"key": legitime.public_key()})()})()
        os.environ["SUPABASE_URL"] = origine

        try:
            A.utilisateur_courant(
                f"Bearer {_jeton_es256(uids['cdg'], attaquant, origine)}")
            raise AssertionError("FAILLE : jeton ES256 contrefait accepté")
        except HTTPException as e:
            assert e.status_code == 401, f"attendu 401, obtenu {e.status_code}"
    finally:
        A._client_jwks = ancien
        A._client_jwks.cache_clear()
        os.environ.pop("SUPABASE_URL", None)
        _nettoyer()


def test_algorithme_none_refuse():
    """Un jeton `alg: none` (non signé) ne doit jamais passer."""
    import jwt
    from fastapi import HTTPException
    A, uids = _preparer()
    try:
        nu = jwt.encode({"sub": uids["cdg"], "aud": "authenticated"},
                        key="", algorithm="none")
        try:
            A.utilisateur_courant(f"Bearer {nu}")
            raise AssertionError("FAILLE : jeton non signé (alg none) accepté")
        except HTTPException as e:
            assert e.status_code == 401, f"attendu 401, obtenu {e.status_code}"
    finally:
        _nettoyer()


if __name__ == "__main__":
    D.sortir(D.lancer("Securite API (cloisonnement agence)", [
        (test_jeton_resout_le_bon_profil,        "jeton Supabase -> role + agence"),
        (test_agence_ne_voit_que_son_agence,     "une AGENCE ne voit que son agence"),
        (test_endpoints_globaux_refuses_a_une_agence, "endpoints globaux refuses a une AGENCE (403)"),
        (test_endpoint_decaissements_ne_fuite_pas_le_global,
         "/decaissements : ni detail ni total des autres agences"),
        (test_jeton_es256_accepte,               "jeton ES256 (cles de signature) accepte"),
        (test_jeton_es256_contrefait_rejete,     "jeton ES256 contrefait rejete (401)"),
        (test_algorithme_none_refuse,            "jeton non signe (alg none) refuse (401)"),
        (test_jeton_contrefait_rejete,           "jeton contrefait rejete (401)"),
        (test_sans_jeton_refuse,                 "aucun endpoint ouvert sans jeton (401)"),
        (test_utilisateur_inactif_refuse,        "compte desactive refuse (403)"),
    ]))