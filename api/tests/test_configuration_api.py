"""
Tests des endpoints de configuration (api/configuration.py).

POURQUOI CE TEST EXISTE : cette page ÉCRIT des intrants dont dépend tout le
reste. Une saisie acceptée de travers ne provoque aucune erreur — elle produit
des chiffres faux, publiables. Trois pièges sont gardés ici :

  1. Un taux de réintégration saisi en POURCENT (50) au lieu d'une fraction
     (0,5) multiplierait l'IBP par cent. L'API doit refuser.
  2. Fermer une agence sans date de fermeture laisserait un portefeuille gelé
     sans point de départ. L'API doit refuser. Et fermer ne doit EFFACER ni le
     nom, ni la région, ni la date d'ouverture.
  3. L'AUDIT lit tout mais n'écrit rien : un contrôleur ne remplit pas ce qu'il
     contrôle.

Base SQLite temporaire, aucun accès réseau.

Lancer :  python tests/test_configuration_api.py
"""
import datetime as dt
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import donnees_test as D   # noqa: E402

DB = "socle/test_configuration.db"
ARRETE = "2026-05-31"
AGENCE = "AGENCE DE GOMA"


def _preparer():
    from socle.schema import (init_db, get_session, fermer_moteurs, DimAgence,
                              Utilisateur)

    os.environ.pop("DATABASE_URL", None)
    fermer_moteurs()
    if os.path.exists(DB):
        try:
            os.remove(DB)
        except PermissionError as e:
            raise AssertionError(f"{DB} verrouillé : session non refermée. {e}")
    init_db(DB)

    s = get_session(DB)
    for login, role, agence in (("cdg", "CDG", None), ("direction", "DIRECTION", None),
                                ("victoire", "AGENCE", "AGENCE DE VICTOIRE"),
                                ("audit", "AUDIT", None)):
        s.add(Utilisateur(login=login, nom_complet=login, mot_de_passe_hash="supabase",
                          sel="supabase", role=role, agence=agence, actif=True,
                          date_creation=dt.date.today(), auth_uid=str(uuid.uuid4())))
    # Une agence avec un référentiel complet : fermer ne doit rien en perdre.
    s.add(DimAgence(code_agence=AGENCE, nom="Goma", region="Nord-Kivu",
                    statut="ACTIVE", date_ouverture=dt.date(2015, 3, 1)))
    s.commit()
    s.close()

    #  Tout passe par get_session : on le fait pointer sur la base de test.
    import configuration as C
    import ingest.taux_change as TC
    import ingest.provision_manuelle as PM
    import ingest.import_budget as IB
    origine = get_session
    for module in (C, TC, PM, IB):
        module.get_session = lambda *a, **k: origine(DB)
    # init_db est appelé par les fonctions d'ingestion avec le chemin par défaut.
    for module in (TC, PM, IB):
        module.init_db = lambda *a, **k: None
    return C


def _nettoyer():
    from socle.schema import fermer_moteurs
    fermer_moteurs()
    if os.path.exists(DB):
        try:
            os.remove(DB)
        except PermissionError:
            pass


def _u(role: str) -> dict:
    return {"login": role.lower(), "role": role,
            "agence": "AGENCE DE VICTOIRE" if role == "AGENCE" else None}


def _attendre_http(code_attendu, appel, quoi):
    from fastapi import HTTPException
    try:
        appel()
    except HTTPException as e:
        assert e.status_code == code_attendu, \
            f"{quoi} : attendu {code_attendu}, obtenu {e.status_code} ({e.detail})"
        return
    raise AssertionError(f"{quoi} : aucune erreur levée, {code_attendu} attendu")


# ─────────────────────────────────────────────────────────────────────────────
def test_taux_saisi_puis_relu():
    C = _preparer()
    try:
        C.poser_taux({"date_effet": "2026-05-01", "taux": 2265.5}, user=_u("CDG"))
        vue = C.configuration_arrete(ARRETE, user=_u("CDG"))
        assert vue["taux_change"]["taux"] == 2265.5, vue["taux_change"]
        assert vue["taux_change"]["du_mois_de_l_arrete"] is True, vue["taux_change"]
    finally:
        _nettoyer()


def test_taux_d_un_autre_mois_est_signale():
    """Un taux applique hors de son mois passe, mais ne doit pas passer inaperçu."""
    C = _preparer()
    try:
        C.poser_taux({"date_effet": "2026-01-01", "taux": 2200.0}, user=_u("CDG"))
        vue = C.configuration_arrete(ARRETE, user=_u("CDG"))
        assert vue["taux_change"]["taux"] == 2200.0
        assert vue["taux_change"]["du_mois_de_l_arrete"] is False, vue["taux_change"]
    finally:
        _nettoyer()


def test_taux_negatif_ou_nul_refuse():
    C = _preparer()
    try:
        _attendre_http(422, lambda: C.poser_taux(
            {"date_effet": "2026-05-01", "taux": 0}, user=_u("CDG")), "taux nul")
        _attendre_http(400, lambda: C.poser_taux(
            {"date_effet": "2026-05-01", "taux": "deux mille"}, user=_u("CDG")),
            "taux illisible")
    finally:
        _nettoyer()


def test_reintegration_en_pourcent_refusee():
    """50 au lieu de 0,5 multiplierait l'IBP par cent : l'API doit refuser."""
    C = _preparer()
    try:
        _attendre_http(422, lambda: C.poser_reintegration(
            {"date_effet": "2026-01-01", "compte_ou_ligne": "communication",
             "taux_reintegration": 50}, user=_u("CDG")), "taux en pourcent")

        C.poser_reintegration({"date_effet": "2026-01-01",
                               "compte_ou_ligne": "communication",
                               "taux_reintegration": 0.5}, user=_u("CDG"))
        vue = C.configuration_arrete(ARRETE, user=_u("CDG"))
        grille = {r["compte_ou_ligne"]: r["taux_reintegration"] for r in vue["reintegrations"]}
        assert grille["communication"] == 0.5, grille
    finally:
        _nettoyer()


def test_provision_manuelle_tracee_puis_retiree():
    C = _preparer()
    try:
        C.poser_provision({"date_arrete": ARRETE, "agence": AGENCE,
                           "montant": 232632.94, "note": "16 % valide DAF"},
                          user=_u("CDG"))
        vue = C.configuration_arrete(ARRETE, user=_u("CDG"))
        prov = vue["provisions_manuelles"]
        assert len(prov) == 1, prov
        assert abs(prov[0]["montant"] - 232632.94) < 0.01, prov
        #  Tracé au login REEL, jamais a une valeur fournie par l'appelant.
        assert prov[0]["saisi_par"] == "cdg", prov[0]
        assert prov[0]["horodatage"] is not None, prov[0]

        C.retirer_provision(arrete=ARRETE, agence=AGENCE, user=_u("CDG"))
        vue = C.configuration_arrete(ARRETE, user=_u("CDG"))
        assert vue["provisions_manuelles"] == [], vue["provisions_manuelles"]

        _attendre_http(404, lambda: C.retirer_provision(
            arrete=ARRETE, agence=AGENCE, user=_u("CDG")), "retrait deja fait")
    finally:
        _nettoyer()


def test_mapping_budget_ajoute_modifie_supprime():
    C = _preparer()
    try:
        C.poser_mapping_budget({"numero_compte": "6.0.2.0.1",
                                "ligne_budgetaire": "Frais de personnel",
                                "sens": "charge"}, user=_u("CDG"))
        vue = C.lire_mapping_budget(user=_u("CDG"))
        assert vue["nb_comptes"] == 1 and vue["nb_charges"] == 1, vue

        #  Reaffectation : le compte change de ligne, il ne se duplique pas.
        C.poser_mapping_budget({"numero_compte": "6.0.2.0.1",
                                "ligne_budgetaire": "Charges du personnel",
                                "sens": "charge"}, user=_u("CDG"))
        vue = C.lire_mapping_budget(user=_u("CDG"))
        assert vue["nb_comptes"] == 1, vue
        assert vue["lignes"][0]["ligne_budgetaire"] == "Charges du personnel", vue["lignes"]

        _attendre_http(422, lambda: C.poser_mapping_budget(
            {"numero_compte": "7.0.1", "ligne_budgetaire": "X", "sens": "recette"},
            user=_u("CDG")), "sens invalide")

        C.retirer_mapping_budget(numero_compte="6.0.2.0.1", user=_u("CDG"))
        assert C.lire_mapping_budget(user=_u("CDG"))["nb_comptes"] == 0
    finally:
        _nettoyer()


def test_fermer_une_agence_conserve_son_referentiel():
    """Fermer n'efface ni le nom, ni la région, ni la date d'ouverture."""
    C = _preparer()
    try:
        _attendre_http(422, lambda: C.enregistrer_une_agence(
            {"code_agence": AGENCE, "statut": "FERMEE"}, user=_u("CDG")),
            "fermeture sans date")

        r = C.enregistrer_une_agence(
            {"code_agence": AGENCE, "statut": "FERMEE",
             "date_fermeture": "2025-01-01", "motif": "Occupation M23"},
            user=_u("CDG"))
        assert r["statut"] == "FERMEE", r
        assert r["nom"] == "Goma", f"le nom a ete efface par la fermeture : {r}"
        assert r["region"] == "Nord-Kivu", f"la region a ete effacee : {r}"
        assert r["date_ouverture"] == dt.date(2015, 3, 1), f"date d'ouverture perdue : {r}"
    finally:
        _nettoyer()


def test_rouvrir_efface_fermeture_et_motif():
    C = _preparer()
    try:
        C.enregistrer_une_agence(
            {"code_agence": AGENCE, "statut": "FERMEE",
             "date_fermeture": "2025-01-01", "motif": "Occupation M23"}, user=_u("CDG"))
        r = C.enregistrer_une_agence({"code_agence": AGENCE, "statut": "ACTIVE"},
                                     user=_u("CDG"))
        assert r["statut"] == "ACTIVE", r
        assert r["date_fermeture"] is None, f"fermeture revolue conservee : {r}"
        assert r["motif"] is None, f"motif revolu conserve : {r}"
        assert r["nom"] == "Goma", r
    finally:
        _nettoyer()


def test_creation_d_une_agence_inconnue():
    C = _preparer()
    try:
        r = C.enregistrer_une_agence(
            {"code_agence": "AGENCE DE KIKWIT", "nom": "Kikwit", "region": "Kwilu"},
            user=_u("CDG"))
        assert r["statut"] == "ACTIVE", r     # une agence nait ACTIVE
        codes = {a["code_agence"] for a in C.lister_agences(user=_u("CDG"))["agences"]}
        assert "AGENCE DE KIKWIT" in codes, codes
    finally:
        _nettoyer()


def test_roles_lecture_et_ecriture():
    """L'AUDIT constate, il ne parametre pas. L'AGENCE ne voit que la sienne."""
    C = _preparer()
    try:
        #  Lecture : l'AUDIT y a droit.
        assert C.configuration_arrete(ARRETE, user=_u("AUDIT")) is not None
        assert C.lire_mapping_budget(user=_u("AUDIT"))["nb_comptes"] == 0

        #  Ecriture : refusee a l'AUDIT comme a l'AGENCE.
        for role in ("AUDIT", "AGENCE"):
            _attendre_http(403, lambda r=role: C.poser_taux(
                {"date_effet": "2026-05-01", "taux": 2265.5}, user=_u(r)),
                f"{role} a saisi un taux")
            _attendre_http(403, lambda r=role: C.enregistrer_une_agence(
                {"code_agence": AGENCE, "statut": "ACTIVE"}, user=_u(r)),
                f"{role} a modifie une agence")

        #  Lecture du referentiel d'agences : l'AGENCE ne voit QUE la sienne.
        C.enregistrer_une_agence({"code_agence": "AGENCE DE VICTOIRE"}, user=_u("CDG"))
        vues = C.lister_agences(user=_u("AGENCE"))["agences"]
        assert [a["code_agence"] for a in vues] == ["AGENCE DE VICTOIRE"], vues

        #  La configuration d'arrete, elle, lui est fermee : ce sont des agregats.
        _attendre_http(403, lambda: C.configuration_arrete(ARRETE, user=_u("AGENCE")),
                       "AGENCE a lu la configuration d'arrete")
    finally:
        _nettoyer()


if __name__ == "__main__":
    D.sortir(D.lancer("Configuration (taux, provisions, reintegrations, agences)", [
        (test_taux_saisi_puis_relu,              "taux saisi puis relu a l'arrete"),
        (test_taux_d_un_autre_mois_est_signale,  "taux d'un autre mois : signale, pas tu"),
        (test_taux_negatif_ou_nul_refuse,        "taux nul ou illisible refuse"),
        (test_reintegration_en_pourcent_refusee, "reintegration en % refusee (IBP x100)"),
        (test_provision_manuelle_tracee_puis_retiree,
         "provision manuelle tracee (qui/quand), puis retiree"),
        (test_mapping_budget_ajoute_modifie_supprime,
         "mapping budgetaire : ajout, reaffectation, suppression"),
        (test_fermer_une_agence_conserve_son_referentiel,
         "fermer une agence conserve nom, region et date d'ouverture"),
        (test_rouvrir_efface_fermeture_et_motif, "rouvrir efface fermeture et motif"),
        (test_creation_d_une_agence_inconnue,    "un code inconnu cree l'agence (ACTIVE)"),
        (test_roles_lecture_et_ecriture,         "AUDIT lit sans ecrire ; AGENCE cloisonnee"),
    ]))
