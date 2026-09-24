"""
Tests de l'endpoint d'import (POST /import/{domaine}) — api/import_cbs.py.

POURQUOI CE TEST EXISTE : c'est le PREMIER endpoint qui ÉCRIT dans le socle. Tout ce que
les autres tests protègent (écart nul, idempotence, cloisonnement) suppose que la base
contient ce qu'on croit y avoir mis. Un import ouvert au mauvais rôle, un fichier accepté
alors qu'il n'est pas le bon, ou un ré-import qui duplique au lieu de remplacer, et les
chiffres deviennent faux SANS message d'erreur.

Il ne nécessite NI Supabase NI données réelles : base SQLite temporaire, jetons JWT forgés,
et une extraction crédit minuscule fabriquée à la volée (en-tête A→AF, 2 prêts).

Lancer :  python tests/test_import_api.py
"""
import datetime as dt
import io
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import donnees_test as D   # noqa: E402  (compte rendu honnete : PASSE / SAUTE / ECHEC)

SECRET_TEST = "secret-jwt-de-test-uniquement-pour-les-tests-locaux"
DB = "socle/test_import.db"

ARRETE = dt.date(2026, 5, 30)
AGENCE_TESTEE = "AGENCE DE VICTOIRE"


# ─────────────────────────────────────────────────────────────────────────────
# Préparation : base de test, utilisateurs des quatre rôles, modules reroutés
# ─────────────────────────────────────────────────────────────────────────────
def _preparer():
    """Base SQLite de test + un utilisateur par rôle + import_cbs branché dessus."""
    from socle.schema import init_db, get_session, fermer_moteurs, Utilisateur

    # Comme dans test_securite_api : le nettoyage vient APRÈS l'import de socle.schema,
    # qui charge api/.env — sinon le .env réel re-remplit l'environnement.
    os.environ["SUPABASE_JWT_SECRET"] = SECRET_TEST
    os.environ.pop("DATABASE_URL", None)      # forcer le repli SQLite local
    os.environ.pop("SUPABASE_URL", None)      # régime HS256 (jetons forgés sans `iss`)

    fermer_moteurs()                          # libérer le fichier (verrou Windows)
    if os.path.exists(DB):
        os.remove(DB)
    init_db(DB)

    uids = {r: str(uuid.uuid4()) for r in ("cdg", "direction", "victoire", "audit")}
    s = get_session(DB)
    for login, role, agence in (("cdg", "CDG", None), ("direction", "DIRECTION", None),
                                ("victoire", "AGENCE", AGENCE_TESTEE),
                                ("audit", "AUDIT", None)):
        s.add(Utilisateur(login=login, nom_complet=login, mot_de_passe_hash="supabase",
                          sel="supabase", role=role, agence=agence, actif=True,
                          date_creation=dt.date.today(), auth_uid=uids[login]))
    s.commit()
    s.close()

    import auth_supabase as A
    import import_cbs as I
    origine = A.get_session
    A.get_session = lambda *a, **k: origine(DB)     # résolution du jeton → base de test
    I.get_session = lambda *a, **k: origine(DB)     # journal des imports → base de test

    # Les fonctions d'ingestion écrivent dans la base par défaut : on les relie à la base
    # de test, sans toucher au reste du domaine (extensions, paramètres requis…).
    # On repart TOUJOURS du catalogue d'origine : chaque test appelle _preparer(), et
    # emballer un catalogue déjà emballé passerait deux fois db_path à l'ingestion.
    global _DOMAINES_ORIGINE
    if _DOMAINES_ORIGINE is None:
        _DOMAINES_ORIGINE = dict(I.DOMAINES)
    import dataclasses
    I.DOMAINES = {
        cle: dataclasses.replace(spec, fonction=_vers_base_de_test(spec.fonction))
        for cle, spec in _DOMAINES_ORIGINE.items()
    }
    return A, I, uids


_DOMAINES_ORIGINE = None


def _vers_base_de_test(fonction):
    def appel(chemin, **kwargs):
        return fonction(chemin, db_path=DB, **kwargs)
    return appel


def _nettoyer():
    from socle.schema import fermer_moteurs
    fermer_moteurs()
    if os.path.exists(DB):
        try:
            os.remove(DB)
        except PermissionError:
            pass


def _jeton(uid: str, secret: str = SECRET_TEST) -> str:
    import jwt
    return jwt.encode({"sub": uid, "aud": "authenticated", "role": "authenticated",
                       "exp": int(dt.datetime.now().timestamp()) + 3600},
                      secret, algorithm="HS256")


# ─────────────────────────────────────────────────────────────────────────────
# Fabrication d'une extraction crédit minuscule (en-tête A→AF, 2 prêts)
# ─────────────────────────────────────────────────────────────────────────────
def _classeur_credit(nb_prets=2, entete_valide=True) -> bytes:
    import openpyxl
    from ingest.import_credit import COLONNES

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Worksheet"
    entetes = list(COLONNES)
    if not entete_valide:
        entetes[1] = "colonne inattendue"       # l'import doit refuser le fichier
    ws.append(entetes)
    for i in range(nb_prets):
        ligne = [""] * len(COLONNES)
        ligne[0] = AGENCE_TESTEE                # agence
        ligne[1] = f"D-{i:03d}"                 # numero_dossier
        ligne[2] = f"C-{i:03d}"                 # numero_client
        ligne[3] = f"CLIENT {i}"                # nom_client
        ligne[4] = "PRET INDIVIDUEL"            # produit_credit
        ligne[5] = 1000.0                       # montant_debourse
        ligne[6] = "10/05/2026"                 # date_deboursement (texte JJ/MM/AAAA)
        ligne[7] = "10/11/2026"                 # date_fin_echeance
        ligne[8] = "AGENT X"                    # agent_credit
        ligne[17] = 800.0                       # encours
        ligne[21] = 45                          # jours_de_retard
        ws.append(ligne)
    tampon = io.BytesIO()
    wb.save(tampon)
    return tampon.getvalue()


def _appeler(I, domaine, *, nom, contenu, user, **parametres):
    """Appelle l'endpoint comme le ferait FastAPI : TOUS les champs sont fournis.

    Les paramètres non passés valent `Form(None)` dans la signature — un objet, pas
    None. Les omettre ici ferait croire à l'endpoint qu'on lui envoie six champs.
    """
    from fastapi import UploadFile
    champs = {"date_arrete": None, "date_effet": None, "feuille": None,
              "feuille_charges": None, "feuille_produits": None,
              "devise": None, "exercice": None, "hypothese": None}
    champs.update(parametres)
    return I.endpoint_import(domaine,
                             fichier=UploadFile(file=io.BytesIO(contenu), filename=nom),
                             user=user, **champs)


def _utilisateur(A, uids, login):
    return A.utilisateur_courant(f"Bearer {_jeton(uids[login])}")


def _compter_credits(arrete=ARRETE) -> int:
    from sqlalchemy import select, func
    from socle.schema import FaitCredit, get_session
    s = get_session(DB)
    try:
        return s.execute(select(func.count()).select_from(FaitCredit)
                         .where(FaitCredit.date_arrete == arrete)).scalar_one()
    finally:
        s.close()


# ─────────────────────────────────────────────────────────────────────────────
# Cas
# ─────────────────────────────────────────────────────────────────────────────
def test_import_credit_charge_reellement():
    """Le fichier envoyé doit se retrouver dans fait_credit, à la bonne date d'arrêté."""
    A, I, uids = _preparer()
    try:
        r = _appeler(I, "credit", nom="extraction_mai.xlsx", contenu=_classeur_credit(2),
                     user=_utilisateur(A, uids, "cdg"), date_arrete="2026-05-30")
        assert r["lignes_chargees"] == 2, r
        assert r["resultat"]["rejetees"] == 0, r
        assert r["importe_par"] == "cdg", r
        assert _compter_credits() == 2, "les prêts ne sont pas dans la base"
    finally:
        _nettoyer()


def test_reimport_remplace_sans_dupliquer():
    """Ré-importer le MÊME arrêté remplace le snapshot (règle I-4), il ne s'ajoute pas.

    C'est l'invariant qui empêche un encours de doubler parce qu'un opérateur a cliqué
    deux fois. La purge est celle de socle/historisation, l'endpoint ne fait que la
    laisser opérer — et en rend compte (`purges`).
    """
    A, I, uids = _preparer()
    try:
        cdg = _utilisateur(A, uids, "cdg")
        _appeler(I, "credit", nom="extraction_mai.xlsx", contenu=_classeur_credit(2),
                 user=cdg, date_arrete="2026-05-30")
        r2 = _appeler(I, "credit", nom="extraction_mai.xlsx", contenu=_classeur_credit(2),
                      user=cdg, date_arrete="2026-05-30")
        assert r2["resultat"]["purges"] == 2, f"purge attendue de 2 lignes : {r2}"
        assert _compter_credits() == 2, \
            f"DOUBLON : {_compter_credits()} prêts après deux imports identiques"
    finally:
        _nettoyer()


def test_import_refuse_aux_roles_sans_ecriture():
    """AGENCE et AUDIT ne doivent PAS pouvoir alimenter la base (403).

    L'AUDIT a un accès total en LECTURE : s'il partageait l'ensemble de rôles des
    endpoints de lecture, il pourrait importer — c'est-à-dire alimenter ce qu'il
    contrôle. D'où ROLES_ECRITURE, distinct de ROLES_ACCES_TOTAL.
    """
    from fastapi import HTTPException
    A, I, uids = _preparer()
    try:
        for login in ("victoire", "audit"):
            try:
                _appeler(I, "credit", nom="x.xlsx", contenu=_classeur_credit(1),
                         user=_utilisateur(A, uids, login), date_arrete="2026-05-30")
                raise AssertionError(f"FUITE : le rôle de {login} a pu importer")
            except HTTPException as e:
                assert e.status_code == 403, f"{login} : attendu 403, obtenu {e.status_code}"
        assert _compter_credits() == 0, "une ligne a été écrite malgré le refus"

        # DIRECTION, elle, doit passer.
        r = _appeler(I, "credit", nom="x.xlsx", contenu=_classeur_credit(1),
                     user=_utilisateur(A, uids, "direction"), date_arrete="2026-05-30")
        assert r["lignes_chargees"] == 1, r
    finally:
        _nettoyer()


def test_fichier_qui_n_est_pas_le_bon_repond_400():
    """Un fichier au mauvais format répond 400, jamais 404 ni 500.

    Le gestionnaire ValueError global de main.py traduit « donnée absente » en 404.
    Appliqué à un import, il ferait dire « cet arrêté n'existe pas » à un fichier qui
    n'a simplement pas les bonnes colonnes — l'opérateur chercherait au mauvais endroit.
    """
    from fastapi import HTTPException
    A, I, uids = _preparer()
    try:
        try:
            _appeler(I, "credit", nom="pas_la_bonne_extraction.xlsx",
                     contenu=_classeur_credit(2, entete_valide=False),
                     user=_utilisateur(A, uids, "cdg"), date_arrete="2026-05-30")
            raise AssertionError("un fichier au mauvais en-tête a été accepté")
        except HTTPException as e:
            assert e.status_code == 400, f"attendu 400, obtenu {e.status_code} ({e.detail})"
            assert "en-t" in str(e.detail).lower() or "requise" in str(e.detail).lower(), \
                f"le message n'explique pas ce qui cloche : {e.detail}"
        assert _compter_credits() == 0
    finally:
        _nettoyer()


def test_extension_inattendue_refusee():
    """On n'ouvre pas un .csv comme une extraction crédit, ni un exécutable comme un tableur."""
    from fastapi import HTTPException
    A, I, uids = _preparer()
    try:
        for nom in ("extraction.csv", "extraction.exe", "extraction"):
            try:
                _appeler(I, "credit", nom=nom, contenu=b"peu importe",
                         user=_utilisateur(A, uids, "cdg"), date_arrete="2026-05-30")
                raise AssertionError(f"extension acceptée à tort : {nom}")
            except HTTPException as e:
                assert e.status_code == 400, f"{nom} : attendu 400, obtenu {e.status_code}"
    finally:
        _nettoyer()


def test_nom_de_fichier_ne_peut_pas_sortir_du_dossier():
    """Un nom venu du navigateur ne doit jamais désigner un autre dossier (traversée)."""
    from fastapi import HTTPException
    import import_cbs as I
    assert I._nom_sain("../../../etc/passwd.xlsx", I.TABLEUR) == "passwd.xlsx"
    assert I._nom_sain("..\\..\\windows\\evil.xlsx", I.TABLEUR) == "evil.xlsx"
    for interdit in ("../../..", "...", "   "):
        try:
            I._nom_sain(interdit, I.TABLEUR)
            raise AssertionError(f"nom accepté à tort : {interdit!r}")
        except HTTPException as e:
            assert e.status_code == 400
    # Le nom reste LISIBLE : il part dans import_log (traçabilité, règle I-9).
    assert I._nom_sain("Extraction Crédit (mai).xlsx", I.TABLEUR) == "Extraction Cr_dit (mai).xlsx"


def test_parametre_inattendu_refuse():
    """`devise` n'a pas de sens pour le crédit : le prendre en silence serait pire.

    Envoyer devise=CDF au domaine crédit chargerait des montants USD étiquetés USD
    sans un mot, et le bilan en CDF serait bâti sur une conversion déjà faite.
    """
    from fastapi import HTTPException
    A, I, uids = _preparer()
    try:
        try:
            _appeler(I, "credit", nom="x.xlsx", contenu=_classeur_credit(1),
                     user=_utilisateur(A, uids, "cdg"),
                     date_arrete="2026-05-30", devise="CDF")
            raise AssertionError("paramètre hors domaine accepté en silence")
        except HTTPException as e:
            assert e.status_code == 422, f"attendu 422, obtenu {e.status_code}"
            assert "devise" in str(e.detail)
        # Le même paramètre est en revanche légitime pour la balance.
        assert "devise" in I.DOMAINES["balance"].optionnels
    finally:
        _nettoyer()


def test_parametres_obligatoires_et_domaine_inconnu():
    """Sans date d'arrêté : 422. Domaine inexistant : 404, avec la liste des domaines."""
    from fastapi import HTTPException
    A, I, uids = _preparer()
    try:
        cdg = _utilisateur(A, uids, "cdg")
        try:
            _appeler(I, "credit", nom="x.xlsx", contenu=_classeur_credit(1), user=cdg)
            raise AssertionError("import accepté sans date d'arrêté")
        except HTTPException as e:
            assert e.status_code == 422 and "date_arrete" in str(e.detail), e.detail

        try:
            _appeler(I, "credit", nom="x.xlsx", contenu=_classeur_credit(1), user=cdg,
                     date_arrete="30/05/2026")
            raise AssertionError("date au mauvais format acceptée")
        except HTTPException as e:
            assert e.status_code == 422, e.status_code

        try:
            _appeler(I, "comptabilite_magique", nom="x.xlsx",
                     contenu=_classeur_credit(1), user=cdg, date_arrete="2026-05-30")
            raise AssertionError("domaine inconnu accepté")
        except HTTPException as e:
            assert e.status_code == 404 and "credit" in str(e.detail), e.detail
    finally:
        _nettoyer()


def test_fichier_trop_volumineux_refuse():
    """Le plafond doit s'appliquer PENDANT l'écriture, pas après avoir tout avalé."""
    from fastapi import HTTPException
    A, I, uids = _preparer()
    plafond = I.TAILLE_MAX_MO
    try:
        I.TAILLE_MAX_MO = 0                      # tout envoi dépasse
        try:
            _appeler(I, "credit", nom="x.xlsx", contenu=b"0" * 4096,
                     user=_utilisateur(A, uids, "cdg"), date_arrete="2026-05-30")
            raise AssertionError("fichier au-delà du plafond accepté")
        except HTTPException as e:
            assert e.status_code == 413, f"attendu 413, obtenu {e.status_code}"
    finally:
        I.TAILLE_MAX_MO = plafond
        _nettoyer()


def test_journal_dit_qui_a_importe():
    """import_log doit nommer l'auteur de l'import (règle I-9) et le journal le renvoyer."""
    A, I, uids = _preparer()
    try:
        _appeler(I, "credit", nom="extraction_mai.xlsx", contenu=_classeur_credit(2),
                 user=_utilisateur(A, uids, "cdg"), date_arrete="2026-05-30")
        journal = I.endpoint_journal(limite=20, user=_utilisateur(A, uids, "audit"))
        lignes = [l for l in journal["imports"] if l["domaine"] == "credit"]
        assert lignes, "aucune ligne de journal pour l'import crédit"
        assert "cdg" in (lignes[0]["message"] or ""), lignes[0]
        assert lignes[0]["fichier"] == "extraction_mai.xlsx", lignes[0]
        assert lignes[0]["acceptees"] == 2, lignes[0]
    finally:
        _nettoyer()


def test_journal_et_catalogue_respectent_les_roles():
    """Le catalogue des domaines est réservé à qui peut importer ; le journal, aux
    rôles à accès total (l'AGENCE ne voit ni l'un ni l'autre)."""
    from fastapi import HTTPException
    A, I, uids = _preparer()
    try:
        agence = _utilisateur(A, uids, "victoire")
        for appel in (lambda: I.endpoint_domaines(user=agence),
                      lambda: I.endpoint_journal(limite=5, user=agence)):
            try:
                appel()
                raise AssertionError("FUITE : un rôle AGENCE a lu le catalogue ou le journal")
            except HTTPException as e:
                assert e.status_code == 403

        # L'AUDIT lit le journal mais ne doit PAS voir le catalogue d'import.
        audit = _utilisateur(A, uids, "audit")
        assert I.endpoint_journal(limite=5, user=audit)["imports"] == []
        try:
            I.endpoint_domaines(user=audit)
            raise AssertionError("l'AUDIT a lu le catalogue d'import")
        except HTTPException as e:
            assert e.status_code == 403

        catalogue = I.endpoint_domaines(user=_utilisateur(A, uids, "cdg"))
        cles = {d["cle"] for d in catalogue["domaines"]}
        # « budget_mapping » est le mapping compte→ligne, sans lequel le suivi
        # budgetaire affiche un realise a 0,00 sur toutes les lignes.
        # « compte_resultat_agence » : fichier mensuel du CDG, base des primes de direction.
        assert cles == {"credit", "balance", "epargne", "objectifs",
                        "budget", "budget_mapping", "compte_resultat_agence",
                        "taux_change", "remboursements"}, cles
    finally:
        _nettoyer()


def test_env_au_gabarit_refuse_l_import():
    """Un api/.env non complété doit faire REFUSER l'import (503), pas l'écrire ailleurs.

    Sans ce garde-fou, l'import atterrit dans la base SQLite locale pendant que
    l'opérateur croit alimenter Supabase : la plateforme reste vide et personne ne sait
    pourquoi.
    """
    from fastapi import HTTPException
    A, I, uids = _preparer()
    try:
        os.environ["DATABASE_URL"] = "postgresql://postgres:[MOT_DE_PASSE]@db.exemple.supabase.co:5432/postgres"
        try:
            _appeler(I, "credit", nom="x.xlsx", contenu=_classeur_credit(1),
                     user=_utilisateur(A, uids, "cdg"), date_arrete="2026-05-30")
            raise AssertionError("import accepté avec un .env resté au gabarit")
        except HTTPException as e:
            assert e.status_code == 503, f"attendu 503, obtenu {e.status_code}"
    finally:
        os.environ.pop("DATABASE_URL", None)
        _nettoyer()


if __name__ == "__main__":
    D.sortir(D.lancer("Import CBS depuis le web (POST /import)", [
        (test_import_credit_charge_reellement,      "un fichier envoye arrive bien dans fait_credit"),
        (test_reimport_remplace_sans_dupliquer,     "re-import du meme arrete : remplace, ne duplique pas"),
        (test_import_refuse_aux_roles_sans_ecriture, "AGENCE et AUDIT ne peuvent pas importer (403)"),
        (test_fichier_qui_n_est_pas_le_bon_repond_400, "mauvais fichier -> 400 explicite (ni 404 ni 500)"),
        (test_extension_inattendue_refusee,         "extension inattendue refusee (400)"),
        (test_nom_de_fichier_ne_peut_pas_sortir_du_dossier, "nom de fichier assaini (pas de traversee)"),
        (test_parametre_inattendu_refuse,           "parametre hors domaine refuse (422), jamais ignore"),
        (test_parametres_obligatoires_et_domaine_inconnu, "parametres manquants (422), domaine inconnu (404)"),
        (test_fichier_trop_volumineux_refuse,       "plafond de taille applique (413)"),
        (test_journal_dit_qui_a_importe,            "import_log nomme l'auteur de l'import"),
        (test_journal_et_catalogue_respectent_les_roles, "catalogue et journal cloisonnes par role"),
        (test_env_au_gabarit_refuse_l_import,       "api/.env au gabarit -> import refuse (503)"),
    ]))
