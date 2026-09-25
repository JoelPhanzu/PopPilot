"""
Tests : import en masse (outils/import_masse.py) sur une base SQLite jetable.

Garde-fous :
  - le mois vient du NOM du fichier ; nom sans mois ou à deux mois → refus (on ne devine pas) ;
  - deux fichiers pour un même mois → refus AVANT toute écriture ;
  - --a-blanc n'écrit rien ; un fichier aux mauvais en-têtes est signalé KO ;
  - import réel : chaque mois à sa fin de mois, classement des produits appliqué (même
    fonction que le site) ; relance = mois déjà en base SAUTÉS ; --remplacer = réécrit
    sans doublon.
"""
from __future__ import annotations

import datetime as dt
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "outils"))

import donnees_test as D   # noqa: E402

DB = "socle/test_import_masse.db"
ENTETE = ("id_cpte;num_complet_cpte;id_client;id_prod;libel;libelle_niveau;devise;solde_actuel;"
          "solde_debut;solde_fin;montant_depot;montant_retrait;sexe;statut_juridique")


def _inventaire(dossier, nom, n, entete=ENTETE):
    lignes = [entete]
    for i in range(n):
        produit = "Pop Monnaie A Terme" if i % 2 else "Epargne a la carte"
        lignes.append(f"{i};C{i};{i};1;{produit};AGENCE DE VICTOIRE;USD;10,5;0;10,5;10,5;0;F;1")
    with open(os.path.join(dossier, nom), "w", encoding="utf-8-sig") as f:
        f.write("\n".join(lignes))


def test_mois_du_nom():
    import import_masse as M
    ok = {
        "Inventaire dépôt Janvier 2025.csv": dt.date(2025, 1, 31),
        "inventaire_2025-02.csv": dt.date(2025, 2, 28),
        "INVENTAIRE 03-2025.xlsx": dt.date(2025, 3, 31),
        "Inventaire Août 2026 (Inventaire_depot_script).csv": dt.date(2026, 8, 31),
        "inventaire FEV 24.csv": dt.date(2024, 2, 29),
        "Inventaire_depot_202512.csv": dt.date(2025, 12, 31),
        "Inventaire décembre 2025.csv": dt.date(2025, 12, 31),
    }
    for nom, attendu in ok.items():
        assert M.mois_du_nom(nom) == attendu, (nom, M.mois_du_nom(nom))
    for nom in ("inventaire.csv", "Janvier 2025 - Fevrier 2025.csv", "export 17.csv"):
        try:
            M.mois_du_nom(nom)
            raise AssertionError(f"mois deviné pour {nom!r}")
        except ValueError:
            pass


def _compter():
    from sqlalchemy import func, select
    from socle.schema import FaitEpargne, get_session
    s = get_session(DB)
    try:
        return dict(s.execute(select(FaitEpargne.date_arrete, func.count())
                              .group_by(FaitEpargne.date_arrete)).all())
    finally:
        s.close()


def test_import_masse_de_bout_en_bout():
    import import_masse as M
    from socle.schema import FaitEpargne, fermer_moteurs, get_session
    os.environ.pop("DATABASE_URL", None)
    fermer_moteurs()
    if os.path.exists(DB):
        os.remove(DB)
    dossier = tempfile.mkdtemp()
    try:
        _inventaire(dossier, "Inventaire depot Janvier 2025.csv", 4)
        _inventaire(dossier, "Inventaire depot Fevrier 2025.csv", 6)
        _inventaire(dossier, "Inventaire depot Mars 2025.csv", 3)
        # à blanc : tout est vérifié, rien n'est écrit
        assert M.main([dossier, "--base-sqlite", DB, "--a-blanc"]) == 0
        assert _compter() == {}
        # import réel
        assert M.main([dossier, "--base-sqlite", DB, "--oui"]) == 0
        assert _compter() == {dt.date(2025, 1, 31): 4, dt.date(2025, 2, 28): 6,
                              dt.date(2025, 3, 31): 3}, _compter()
        s = get_session(DB)
        types = {t for (t,) in s.query(FaitEpargne.type_depot).distinct()}
        s.close()
        assert types == {"a_vue", "a_terme"}, types              # règles du site appliquées
        # relance : rien à refaire (reprise après coupure)
        _inventaire(dossier, "Inventaire depot Mars 2025.csv", 5)
        assert M.main([dossier, "--base-sqlite", DB, "--oui"]) == 0
        assert _compter()[dt.date(2025, 3, 31)] == 3               # sauté, pas réécrit
        # --remplacer : réécrit sans doublon
        assert M.main([dossier, "--base-sqlite", DB, "--oui", "--remplacer"]) == 0
        assert _compter()[dt.date(2025, 3, 31)] == 5
        # mauvais en-têtes → KO à blanc
        _inventaire(dossier, "Inventaire depot Avril 2025.csv", 2, entete="compte;solde")
        assert M.main([dossier, "--base-sqlite", DB, "--a-blanc"]) == 1   # KO lisible
        os.remove(os.path.join(dossier, "Inventaire depot Avril 2025.csv"))
        # deux fichiers pour le même mois → refus avant toute écriture
        _inventaire(dossier, "Inventaire 2025-01 bis.csv", 9)
        avant = _compter()
        assert M.main([dossier, "--base-sqlite", DB, "--oui", "--remplacer"]) == 1
        assert _compter() == avant
    finally:
        shutil.rmtree(dossier, ignore_errors=True)
        fermer_moteurs()


if __name__ == "__main__":
    code = D.lancer("Import en masse (outils/import_masse.py)", [
        (test_mois_du_nom, "Mois lu dans le nom ; nom ambigu ou sans mois refusé"),
        (test_import_masse_de_bout_en_bout,
         "À blanc sans écriture ; import ; reprise (sauté) ; --remplacer ; doublons de mois refusés"),
    ])
    D.sortir(code)
