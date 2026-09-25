"""Tests épargne — import 170k comptes, ventilation type/devise/groupe, cohérence bilan."""
import datetime as dt
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import donnees_test as D   # localise les sources reelles + compte rendu honnete

from socle.schema import fermer_moteurs
from socle.seed_parametres import seed
from ingest.import_epargne import importer_epargne
from engine.epargne import synthese_epargne, nb_epargnants

INVENTAIRE = "Inventaire_depot_juillet_2026_Inventaire_depot_script___3_"
ARRETE = dt.date(2026, 7, 31)
DB = "socle/test_epargne.db"


def test_import_et_ventilation():
    CSV = D.exiger_un_de(INVENTAIRE + ".csv", INVENTAIRE + ".xlsx")
    fermer_moteurs()
    if os.path.exists(DB):
        os.remove(DB)
    seed(DB)
    r = importer_epargne(CSV, ARRETE, db_path=DB)
    assert r["acceptees"] == 169799
    syn = synthese_epargne(ARRETE, db_path=DB)
    # ventilation cohérente : total = somme des types
    total_types = syn["depots_a_vue"] + syn["depots_a_terme"] + syn["depots_obligatoire"]
    assert abs(total_types - syn["encours_total"]) < 1.0
    # à terme = Pop Monnaie A Terme USD (2 909 946)
    assert abs(syn["depots_a_terme"] - 2909946.25) < 1.0
    # obligatoire = nantie + caution (1 621 222)
    assert abs(syn["depots_obligatoire"] - 1621222.30) < 1.0
    # épargnants proches de la référence FINA
    assert 67000 < nb_epargnants(ARRETE, db_path=DB) < 67300


def test_tableau_de_bord_epargne():
    """Sans filtre, le tableau de bord redonne la synthèse validée au centime ; Σ lignes = total
    à chaque niveau ; les filtres partitionnent ; une date sans inventaire est refusée."""
    from engine.tableau_de_bord_epargne import tableau_de_bord_epargne
    syn = synthese_epargne(ARRETE, db_path=DB)
    r = tableau_de_bord_epargne(ARRETE, db_path=DB)
    g = r["lignes"][0]
    assert abs(g["encours"] - syn["encours_total"]) < 0.01 and g["nb_comptes"] == syn["nb_comptes"]
    assert g["nb_epargnants"] == nb_epargnants(ARRETE, db_path=DB)
    assert abs(g["a_terme"] - syn["depots_a_terme"]) < 0.01
    for niveau in ("agence", "produit", "type"):
        x = tableau_de_bord_epargne(ARRETE, niveau=niveau, db_path=DB)
        reste = x["lignes"][1:]
        assert abs(sum(l["encours"] for l in reste) - g["encours"]) < 0.05, niveau
        assert sum(l["nb_comptes"] for l in reste) == g["nb_comptes"], niveau
        assert abs(sum(l["depots"] for l in reste) - g["depots"]) < 0.05, niveau
    assert r["mois_de_flux"] == ["2026-07-31"] and g["depots"] > 0 and g["retraits"] > 0
    parts = [tableau_de_bord_epargne(ARRETE, filtres={"sexe": s}, db_path=DB)["lignes"][0]
             for s in ("H", "F", "PM")]
    assert sum(p["nb_comptes"] for p in parts) == g["nb_comptes"]
    assert abs(sum(p["encours"] for p in parts) - g["encours"]) < 0.05
    c = tableau_de_bord_epargne(ARRETE, niveau="client", limite=10, db_path=DB)
    assert len(c["lignes"]) == 11 and c["nb_lignes_total"] == g["nb_epargnants"]
    try:
        tableau_de_bord_epargne(dt.date(2026, 6, 30), db_path=DB)
        raise AssertionError("un arrêté sans inventaire aurait dû être refusé")
    except ValueError as e:
        assert "2026-07-31" in str(e)                     # le message cite les inventaires chargés


def test_api_epargne_cloisonnement():
    import epargne_tdb as E
    E.BASE = DB
    agence = "AGENCE DE VICTOIRE"
    r = E.endpoint_tableau_de_bord_epargne(
        arrete=ARRETE.isoformat(), debut=None, fin=None, niveau="agence", limite=300, agence=None,
        devise=None, type_depot=None, sexe=None, groupe=None,
        user={"login": "v", "role": "AGENCE", "agence": agence})
    assert r["lignes"][0]["designation"] == agence
    assert {l["designation"] for l in r["lignes"][1:]} == {agence}
    from fastapi import HTTPException
    try:
        E.endpoint_tableau_de_bord_epargne(
            arrete=ARRETE.isoformat(), debut=None, fin=None, niveau="agence", limite=300,
            agence="AGENCE OZONE", devise=None, type_depot=None, sexe=None, groupe=None,
            user={"login": "v", "role": "AGENCE", "agence": agence})
        raise AssertionError("une autre agence aurait dû être refusée")
    except HTTPException as e:
        assert e.status_code == 403
    top = E.endpoint_top_epargnants(arrete=ARRETE.isoformat(), n=5, agence=None, devise=None,
                                    type_depot=None, sexe=None, groupe=None,
                                    user={"login": "c", "role": "CDG", "agence": None})
    soldes = [c["solde_usd"] for c in top["clients"]]
    assert len(soldes) == 5 and soldes == sorted(soldes, reverse=True)
    # Nom complet de l'inventaire (colonne nom_complet) conservé et restitué (SQL 09)
    noms = [c["nom_client"] for c in top["clients"]]
    assert all(n and n == " ".join(n.split()) for n in noms), noms


def test_statut_noms_couverture_client_produits():
    """Statut juridique (1/2/4) : filtre « personnes morales seulement », partition complète ;
    niveau client : nom, statut, encours crédit DU client et couverture ; niveau produit :
    type et devise de chaque produit tel qu'il figure dans l'inventaire."""
    from engine.tableau_de_bord_epargne import tableau_de_bord_epargne, top_epargnants
    from socle.schema import FaitCredit, get_session
    g = tableau_de_bord_epargne(ARRETE, db_path=DB)["lignes"][0]
    parts = {st: tableau_de_bord_epargne(ARRETE, filtres={"statut": st}, db_path=DB)["lignes"][0]
             for st in ("pp", "pm", "groupe")}
    assert sum(p["nb_comptes"] for p in parts.values()) == g["nb_comptes"]
    assert abs(sum(p["encours"] for p in parts.values()) - g["encours"]) < 0.05
    assert parts["pm"]["nb_epargnants"] == 151 and parts["groupe"]["nb_epargnants"] == 3553
    # PM seulement, sans le lier aux produits de groupe : les deux filtres sont indépendants
    pm_hors_groupe = tableau_de_bord_epargne(ARRETE, filtres={"statut": "pm", "groupe": "non"},
                                             db_path=DB)["lignes"][0]
    assert 0 < pm_hors_groupe["nb_comptes"] <= parts["pm"]["nb_comptes"]
    # niveau client
    c = tableau_de_bord_epargne(ARRETE, niveau="client", db_path=DB, limite=20)["lignes"][1:]
    assert all(l["nom_client"] and l["statut_juridique"] in
               ("Personne physique", "Personne morale", "Groupe solidaire") for l in c)
    # un emprunteur : son encours crédit = extraction crédit du même code client
    s = get_session(DB)
    try:
        emprunteurs = {k for (k,) in s.query(FaitCredit.numero_client).distinct()}
    finally:
        s.close()
    if emprunteurs:
        avec = [l for l in c if l["cle"] in emprunteurs]
        assert all(l["encours_credit"] and l["couverture_credit"] is not None for l in avec)
    # niveau produit : produits tels qu'ils sont dans l'inventaire, avec type et devise
    prod = tableau_de_bord_epargne(ARRETE, niveau="produit", db_path=DB)["lignes"][1:]
    assert len(prod) >= 10 and all(l["type_depot"] in ("À vue", "À terme", "Obligatoire") for l in prod)
    assert {l["designation"] for l in prod} >= {"Pop Monnaie a la Carte CDF", "Pop Monnaie Nantie"}
    top = top_epargnants(ARRETE, 5, {"statut": "pm"}, db_path=DB)
    assert top and all(x["statut_juridique"] == "Personne morale" for x in top)


if __name__ == "__main__":
    D.sortir(D.lancer("Epargne", [
        (test_import_et_ventilation, "170k comptes, ventilation type = regle CDG"),
        (test_tableau_de_bord_epargne, "Tableau de bord epargne = synthese ; Σ lignes ; filtres ; date absente"),
        (test_api_epargne_cloisonnement, "API epargne : AGENCE limitee a son agence ; Top N"),
        (test_statut_noms_couverture_client_produits,
         "Statut juridique (PM seules, partition) ; client : nom, statut, couverture ; produits detailles"),
    ]))