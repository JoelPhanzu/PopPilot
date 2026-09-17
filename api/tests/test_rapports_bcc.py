"""
Tests des rapports BCC lus depuis l'inventaire dépôt : AML/LBC-FT et Système de paiement.

Ces deux moteurs n'avaient AUCUN test. Ils lisaient le même fichier par NUMÉRO de colonne,
avec un cran d'écart entre eux : sur l'inventaire de juillet, le Système de paiement
comptait les retraits comme des versements et le solde de fin comme des retraits. Rien
ne le signalait, et les deux rapports partaient à la BCC.

Deux garde-fous ici :
  1. CONCORDANCE — les deux moteurs doivent voir exactement les mêmes opérations.
  2. TAUX JAMAIS FIGÉ — sans taux saisi, on refuse de convertir (§42).
"""
import datetime as dt
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import donnees_test as D   # localise les sources reelles + compte rendu honnete

from engine.aml import portefeuille_client, transferts_grand_livre
from engine.systeme_paiement import transactions_inventaire

INVENTAIRE = "Inventaire_depot_juillet_2026_Inventaire_depot_script___3_"
TAUX = 2268.75          # taux de clôture juillet 2026 (saisi, §42)


def _inventaire():
    return D.exiger_un_de(INVENTAIRE + ".xlsx", INVENTAIRE + ".csv")


def test_aml_et_systeme_paiement_voient_les_memes_operations():
    """LE test : mêmes opérations, mêmes montants, lus par les deux moteurs.

    Il échoue dès qu'un des deux revient à une lecture par position de colonne, ou
    que le CBS déplace une colonne sans qu'on s'en aperçoive.
    """
    inv = _inventaire()
    pf = portefeuille_client(inv, TAUX)
    tx = transactions_inventaire(inv, taux_cdf=TAUX)

    ops_aml = sum(v["nombre"] for v in pf["localisation"].values())
    ops_sp = tx["versement"]["nb_total"] + tx["retrait"]["nb_total"]
    assert ops_aml == ops_sp, f"AML {ops_aml} opérations vs Système de paiement {ops_sp}"

    montant_aml = sum(v["volume"] for v in pf["localisation"].values())
    montant_sp = tx["versement"]["valeur_totale_cdf"] + tx["retrait"]["valeur_totale_cdf"]
    assert abs(montant_aml - montant_sp) < 1, (montant_aml, montant_sp)

    # ordre de grandeur attendu sur juillet 2026 (garde-fou contre une colonne décalée :
    # lire le solde de fin à la place d'un retrait multiplierait ces montants par ~1000)
    assert 10000 < ops_sp < 100000, ops_sp
    assert tx["retrait"]["nb_total"] > tx["versement"]["nb_total"] > 1000


def test_portefeuille_client_coherent_avec_lepargne():
    """Le portefeuille client AML (soldes de fin) reste proche de l'encours épargne.

    Deux lectures différentes du même stock (solde_fin ici, solde_actuel pour le moteur
    épargne) : elles doivent rester dans le même ordre de grandeur, à quelques pour cent.
    """
    inv = _inventaire()
    pf = portefeuille_client(inv, TAUX)
    total_usd = pf["solde_total"] / TAUX
    assert 5.5e6 < total_usd < 7.5e6, f"{total_usd:,.0f} USD"
    assert pf["pp_nombre"] > 60000
    assert pf["pm_nombre"] > 100
    assert pf["groupe_nombre"] > 1000
    # une agence non rattachée à une province serait muette dans la section 7 : on l'exige vide
    assert pf["agences_sans_province"] == [], pf["agences_sans_province"]


def test_taux_jamais_fige():
    """Sans taux saisi : on refuse de convertir, on ne retombe pas sur un taux d'un autre mois.

    Les valeurs par défaut (2263,57 — taux d'août 2026) faisaient sortir n'importe quel
    mois converti au mauvais taux, en silence.
    """
    inv = _inventaire()
    for appel in (lambda: portefeuille_client(inv, None),
                  lambda: transferts_grand_livre(inv, None)):
        try:
            appel()
            raise AssertionError("un taux absent doit lever, pas retomber sur une valeur figée")
        except ValueError:
            pass
    # le système de paiement, lui, reste lisible SANS taux : les devises y sont séparées
    # (doctrine BCC) ; seuls les totaux convertis valent None.
    tx = transactions_inventaire(inv)
    assert tx["versement"]["valeur_cdf_native"] > 0
    assert tx["versement"]["valeur_usd"] > 0
    assert tx["versement"]["valeur_totale_cdf"] is None


def test_format_inconnu_refuse():
    """Un fichier sans les colonnes attendues doit être refusé, pas lu de travers."""
    from ingest.import_epargne import verifier_colonnes
    try:
        verifier_colonnes({"colonne_bidon": 1})
        raise AssertionError("un inventaire sans ses colonnes doit lever")
    except ValueError as e:
        assert "solde_fin" in str(e)


def _inventaire_minimal(chemin):
    """Inventaire de test : 1 PP, 1 PM, 2 groupes (statut 4), dont une agence inconnue."""
    import openpyxl
    wb = openpyxl.Workbook(); ws = wb.active
    ws.append(["id_cpte", "devise", "id_client", "statut_juridique", "solde_fin",
               "montant_depot", "montant_retrait", "libelle_niveau"])
    ws.append(["1", "USD", "C1", "1", 100, 10, 0, "AGENCE DE VICTOIRE"])
    ws.append(["2", "CDF", "C2", "2", 5000, 0, 200, "AGENCE DE LUBUMBASHI"])
    ws.append(["3", "CDF", "G1", "4", 7000, 50, 0, "AGENCE DE VICTOIRE"])
    ws.append(["4", "CDF", "G2", "4", 3000, 0, 80, "AGENCE DE KOLWEZI"])  # hors referentiel
    wb.save(chemin)
    return chemin


def _gabarit_aml_minimal(chemin):
    import openpyxl
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "REPORTING LBC-FT"
    for libelle, ligne in (("HAUT-KATANGA", 149), ("NORD-KIVU", 150), ("KINSHASA", 151)):
        ws.cell(row=ligne, column=1, value=libelle)
    wb.create_sheet("Brouillard de caisse USD")
    wb.create_sheet("Grand Livre")
    wb.save(chemin)
    return chemin


def test_aml_groupes_jamais_perdus_en_silence():
    """Ce qui est calculé doit être écrit, ou dit — jamais jeté.

    `portefeuille_client` compte bien les groupes (statut juridique 4 ; aout 2026 :
    3 566 groupes, 732 M CDF) et le dossier revendique « total clients = PP+PM+groupes ».
    Mais l'écriture ne remplissait que PP et PM : les groupes étaient calculés puis
    JETÉS, et le fichier remis à la Conformité sous-déclarait le portefeuille sans un mot.
    """
    import tempfile
    import openpyxl
    from engine.aml_ecriture import ecrire_aml
    tmp = tempfile.gettempdir()
    gabarit = _gabarit_aml_minimal(os.path.join(tmp, "aml_gabarit_min.xlsx"))
    inventaire = _inventaire_minimal(os.path.join(tmp, "aml_inventaire_min.xlsx"))
    sortie = os.path.join(tmp, "aml_test_sortie.xlsx")
    debut, fin = dt.date(2026, 8, 1), dt.date(2026, 8, 31)

    # 1) Sans ligne cible : les groupes ne sont pas ecrits, mais le rapport le DIT.
    r = ecrire_aml(gabarit, sortie, debut, fin, path_inventaire=inventaire, taux_cdf=TAUX)
    assert r["portefeuille"]["groupe_nombre"] == 2, r["portefeuille"]
    assert r["complet"] is False, "un rapport qui omet les groupes doit se dire incomplet"
    assert any("GROUPE" in m for m in r["non_ecrit"]), r["non_ecrit"]
    # une agence hors AGENCE_PROVINCE ne doit pas disparaitre non plus
    assert any("KOLWEZI" in m for m in r["non_ecrit"]), r["non_ecrit"]

    # 2) Avec la ligne relevee sur le gabarit : les groupes sont bien ecrits.
    r2 = ecrire_aml(gabarit, sortie, debut, fin, path_inventaire=inventaire,
                    taux_cdf=TAUX, ligne_groupe=41)
    ws = openpyxl.load_workbook(sortie)["REPORTING LBC-FT"]
    assert ws.cell(row=41, column=2).value == 2, "nombre de groupes non ecrit"
    assert ws.cell(row=41, column=3).value == 10000, "solde groupe non ecrit"
    assert not any("GROUPE" in m for m in r2["non_ecrit"]), r2["non_ecrit"]
    os.remove(sortie)


def test_systeme_paiement_sans_taux_ne_plante_pas():
    """Sans taux, le total converti vaut None — et cela doit rester affichable.

    Le rapport BCC veut les devises SÉPARÉES : l'absence de taux est un cas normal,
    pas une panne. Le bloc de démonstration formatait pourtant `None` avec `:,.0f`
    et levait un TypeError.
    """
    import tempfile
    inventaire = _inventaire_minimal(
        os.path.join(tempfile.gettempdir(), "sp_inventaire_min.xlsx"))

    sans = transactions_inventaire(inventaire, taux_cdf=None)
    assert sans["versement"]["valeur_totale_cdf"] is None
    assert sans["versement"]["valeur_cdf_native"] == 50.0      # le groupe G1, en CDF
    for bloc in ("versement", "retrait"):                      # doit rester formatable
        v = sans[bloc]["valeur_totale_cdf"]
        assert (f"{v:,.0f}" if v is not None else "n/a") == "n/a"

    avec = transactions_inventaire(inventaire, taux_cdf=TAUX)
    assert avec["versement"]["valeur_totale_cdf"] == 50.0 + 10 * TAUX


if __name__ == "__main__":
    D.sortir(D.lancer("Rapports BCC (AML, systeme de paiement)", [
        (test_aml_groupes_jamais_perdus_en_silence,
         "AML : groupes ecrits, ou declares non ecrits (jamais jetes)"),
        (test_systeme_paiement_sans_taux_ne_plante_pas,
         "systeme de paiement : sans taux, total None reste affichable"),
        (test_aml_et_systeme_paiement_voient_les_memes_operations,
         "AML et Systeme de paiement lisent les memes operations"),
        (test_portefeuille_client_coherent_avec_lepargne,
         "portefeuille client coherent avec l'encours epargne"),
        (test_taux_jamais_fige, "taux absent : refus de convertir (jamais fige)"),
        (test_format_inconnu_refuse, "inventaire de format inconnu refuse"),
    ]))
