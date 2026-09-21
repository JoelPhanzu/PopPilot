"""
Tests de la génération des rapports réglementaires (api/rapports.py).

POURQUOI CE TEST EXISTE : ces documents PARTENT À LA BANQUE CENTRALE. Un rapport
produit sur une donnée manquante, un taux figé ou une ventilation qui ne
totalise pas 100 % n'a l'air de rien — il a la bonne tête, les bonnes cases
remplies, et il est faux. Chaque cas ci-dessous garde une porte par laquelle un
tel document pourrait sortir.

Le cas `ventilation F10` mérite un mot : les parts sectorielles répartissent un
total RÉEL. Si elles totalisent 0,70 au lieu de 1, la feuille F10 ne déclare que
70 % du crédit, et ne concorde plus avec le même crédit déclaré en F5 et F0 du
MÊME rapport. Rien ne le signale à la lecture.

Aucun accès réseau, aucune donnée réelle : les fichiers sont des leurres, et on
ne teste que ce qui se décide AVANT d'appeler les moteurs (déjà couverts par
test_fina_ecriture.py et test_rapports_bcc.py).

Lancer :  python tests/test_rapports_api.py
"""
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import donnees_test as D   # noqa: E402

CDG = {"login": "cdg", "role": "CDG", "agence": None}
AUDIT = {"login": "audit", "role": "AUDIT", "agence": None}
AGENCE = {"login": "victoire", "role": "AGENCE", "agence": "AGENCE DE VICTOIRE"}


def _envoi(nom: str, octets: int = 64):
    from fastapi import UploadFile
    return UploadFile(file=io.BytesIO(b"x" * octets), filename=nom)


def _attendre(code: int, appel, quoi: str):
    from fastapi import HTTPException
    try:
        appel()
    except HTTPException as e:
        assert e.status_code == code, \
            f"{quoi} : attendu {code}, obtenu {e.status_code} ({e.detail})"
        return str(e.detail)
    raise AssertionError(f"{quoi} : aucune erreur levée, {code} attendu")


# ─────────────────────────────────────────────────────────────────────────────
def test_catalogue_decrit_tout_ce_qu_il_faut_fournir():
    """Le formulaire du front se construit d'ici : rien ne doit y manquer."""
    from rapports import catalogue

    c = catalogue(user=CDG)
    par_cle = {r["cle"]: r for r in c["rapports"]}
    assert set(par_cle) == {"fina", "aml", "systeme_paiement"}, set(par_cle)

    for cle, r in par_cle.items():
        assert r["libelle"] and r["aide"], cle
        assert r["extension_sortie"].startswith("."), cle
        for f in r["fichiers"]:
            assert f["extensions"], f"{cle}/{f['nom']} : aucune extension acceptée"
        for champ in r["champs"]:
            assert champ["type"] in ("date", "texte", "nombre", "entier"), champ

    #  Le système de paiement ne remplit PAS le gabarit officiel : il faut que
    #  la plateforme le dise, sinon on croira la déclaration produite.
    sp = par_cle["systeme_paiement"]
    assert sp["remplit_gabarit"] is False
    assert "ne remplit" in sp["aide"].lower() or "résultats" in sp["aide"].lower(), sp["aide"]


def test_rapport_inconnu_liste_les_rapports():
    from rapports import generer
    message = _attendre(404, lambda: generer("inexistant", user=CDG), "rapport inconnu")
    assert "fina" in message and "aml" in message, message


def test_champ_obligatoire_manquant_est_nomme():
    """Le message doit dire CE QUI manque, pas « date invalide (Form(None)) ».

    Appelée directement, la fonction reçoit ses défauts `Form(None)` sous forme
    d'objets TRUTHY : sans neutralisation, le contrôle des obligatoires les
    prenait pour une saisie et l'erreur tombait plus loin, sur un message
    incompréhensible.
    """
    from rapports import generer
    message = _attendre(422, lambda: generer("fina", gabarit=_envoi("g.xls"), user=CDG),
                        "fina sans arrêté")
    assert "Date d'arrêté" in message, message

    message = _attendre(422, lambda: generer("aml", source=_envoi("s.xlsx"), user=CDG),
                        "aml sans période")
    assert "Début de période" in message and "Fin de période" in message, message


def test_fichier_obligatoire_manquant_est_nomme():
    from rapports import generer
    message = _attendre(422, lambda: generer("fina", arrete="2026-06-30", user=CDG),
                        "fina sans gabarit")
    assert "Gabarit" in message, message

    message = _attendre(
        422,
        lambda: generer("systeme_paiement", dormant=_envoi("d.xlsx"),
                        arrete="2026-08-31", user=CDG),
        "système de paiement sans inventaire")
    assert "Inventaire" in message, message


def test_ventilation_f10_doit_totaliser_cent_pour_cent():
    """Des parts qui ne font pas 1 déclarent une fraction du crédit réel."""
    from rapports import generer
    message = _attendre(
        422,
        lambda: generer("fina", gabarit=_envoi("g.xls"), arrete="2026-06-30",
                        f10_commerce="0.5", f10_services="0.2", user=CDG),
        "F10 incomplète")
    assert "0.7" in message or "0,7" in message, message

    #  Aucune part saisie : c'est permis (le moteur laisse la feuille en l'état).
    #  On doit donc échouer PLUS LOIN, sur la donnée, pas sur la ventilation.
    message = _attendre(
        400,
        lambda: generer("fina", gabarit=_envoi("g.xls"), arrete="2026-06-30", user=CDG),
        "F10 absente")
    assert "F10" not in message, f"la ventilation absente a été refusée : {message}"


def test_periode_aml_dans_le_bon_sens():
    from rapports import generer
    _attendre(422,
              lambda: generer("aml", source=_envoi("s.xlsx"),
                              periode_debut="2026-08-31", periode_fin="2026-08-01",
                              user=CDG),
              "période AML inversée")


def test_extension_inattendue_refusee():
    """Un PDF nommé .pdf ne doit pas atteindre le moteur."""
    from rapports import generer
    message = _attendre(
        400,
        lambda: generer("fina", gabarit=_envoi("gabarit.pdf"), arrete="2026-06-30",
                        user=CDG),
        "gabarit en PDF")
    assert ".xls" in message, message


def test_roles():
    """Générer LIT le socle sans l'écrire : ouvert à l'AUDIT, fermé à l'AGENCE."""
    from rapports import catalogue, generer

    _attendre(403, lambda: catalogue(user=AGENCE), "AGENCE a lu le catalogue")
    _attendre(403,
              lambda: generer("fina", gabarit=_envoi("g.xls"), arrete="2026-06-30",
                              user=AGENCE),
              "AGENCE a généré un rapport")

    assert catalogue(user=AUDIT)["rapports"], "l'AUDIT ne peut pas lire le catalogue"
    #  L'AUDIT va jusqu'au moteur : l'échec qu'il obtient porte sur la DONNÉE,
    #  pas sur son rôle. Recalculer une déclaration pour la vérifier est son métier.
    message = _attendre(
        400,
        lambda: generer("fina", gabarit=_envoi("g.xls"), arrete="2026-06-30", user=AUDIT),
        "AUDIT bloqué avant le moteur")
    assert "403" not in message, message


def test_aucun_fichier_temporaire_ne_survit():
    """Les classeurs reçus contiennent des données clients : rien ne doit rester.

    L'AML reçoit brouillards et grand livre ; les laisser sur le disque du
    serveur après un échec serait une fuite silencieuse.
    """
    import tempfile
    from rapports import generer

    avant = {n for n in os.listdir(tempfile.gettempdir())
             if n.startswith("poppilot_rapport_")}
    for appel in (
        lambda: generer("fina", gabarit=_envoi("g.xls"), arrete="2026-06-30", user=CDG),
        lambda: generer("aml", source=_envoi("s.xlsx"), periode_debut="2026-08-01",
                        periode_fin="2026-08-31", user=CDG),
    ):
        try:
            appel()
        except Exception:                                    # noqa: BLE001
            pass
    apres = {n for n in os.listdir(tempfile.gettempdir())
             if n.startswith("poppilot_rapport_")}
    restes = apres - avant
    assert not restes, f"dossiers de travail non nettoyés après échec : {sorted(restes)}"


if __name__ == "__main__":
    D.sortir(D.lancer("Rapports reglementaires (POST /rapports)", [
        (test_catalogue_decrit_tout_ce_qu_il_faut_fournir,
         "le catalogue decrit fichiers, champs et nature du rapport"),
        (test_rapport_inconnu_liste_les_rapports, "rapport inconnu -> 404 avec la liste"),
        (test_champ_obligatoire_manquant_est_nomme,
         "champ obligatoire manquant : NOMME (pas « Form(None) »)"),
        (test_fichier_obligatoire_manquant_est_nomme, "fichier obligatoire manquant : nomme"),
        (test_ventilation_f10_doit_totaliser_cent_pour_cent,
         "F10 : les parts doivent totaliser 100 % (ou aucune)"),
        (test_periode_aml_dans_le_bon_sens, "periode AML inversee refusee"),
        (test_extension_inattendue_refusee, "extension inattendue refusee"),
        (test_roles, "AUDIT genere (lecture seule) ; AGENCE refusee"),
        (test_aucun_fichier_temporaire_ne_survit,
         "aucun fichier de travail ne survit a un echec"),
    ]))
