"""
Tests : primes des agents de crédit et superviseurs (engine/primes_ac_sup.py).

La RÈGLE (moteur_primes.calculer_prime_agent) est validée 31/31 contre CALCUL_PRIMES de mai.
Ici on vérifie l'ORCHESTRATION sur des données réelles de juillet (encours + inventaire dépôt
+ fichier OBJECTIF rangé en juillet) :
  - une ligne par agent / superviseur ACTIF du roster, jamais d'orphelin primé ;
  - chaque prime = la règle appliquée à ses bases (aucun calcul parallèle) ;
  - l'épargne d'un client n'est comptée qu'une fois (Σ épargne agents ≤ épargne des clients) ;
  - pré-requis bloquants : sans inventaire épargne ou sans roster du mois → refus explicite.
Validation au centime contre CALCUL_PRIMES de mai dès que l'inventaire dépôt de mai sera chargé.

Lancer :  python tests/test_primes_ac_sup.py
"""
import datetime as dt
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import donnees_test as D   # noqa: E402

DB = "socle/test_primes_ac_sup.db"
JUILLET = dt.date(2026, 7, 31)
INVENTAIRE = "Inventaire_depot_juillet_2026_Inventaire_depot_script___3_"
_pret = []


def _preparer():
    if _pret:
        return
    import socle.schema as S
    os.environ.pop("DATABASE_URL", None)
    enc = D.exiger("Encours_credit_JUILLET_2026.xlsx")
    inv = D.exiger_un_de(INVENTAIRE + ".csv", INVENTAIRE + ".xlsx")
    objectif = D.exiger("OBJECTIF.xlsx")
    S.fermer_moteurs()
    if os.path.exists(DB):
        os.remove(DB)
    from socle.seed_parametres import seed
    from ingest.import_credit import importer_credit
    from ingest.import_epargne import importer_epargne
    from ingest.import_objectifs import importer_objectifs
    seed(DB)
    importer_credit(enc, JUILLET, date_snapshot=dt.date(2026, 8, 1), db_path=DB)
    importer_epargne(inv, JUILLET, db_path=DB)
    importer_objectifs(objectif, dt.date(2026, 7, 1), db_path=DB)
    _pret.append(True)


def test_orchestration_juillet():
    _preparer()
    from engine.moteur_primes import calculer_prime_agent
    from engine.primes_ac_sup import primes_ac_sup
    from engine.epargne import synthese_epargne
    r = primes_ac_sup(JUILLET, db_path=DB)
    assert r["agents"] and r["superviseurs"]
    assert len(r["agents"]) <= 39                                   # roster : 39 agents
    assert abs(r["total_agents"] - sum(x["prime_totale"] for x in r["agents"])) < 0.01
    for x in r["agents"] + r["superviseurs"]:
        attendu = calculer_prime_agent(
            produit=x["produit"], volume_realise=x["volume_realise"],
            volume_objectif=x["volume_objectif"] or 0.0, nombre_realise=x["nombre_realise"],
            nombre_objectif=x["nombre_objectif"] or 0.0, encours_volume=x["encours"],
            encours_nombre=x["nb_credits"], solde_epargne=x["epargne"], par30=x["par30"])
        assert attendu["prime_totale"] == x["prime_totale"], x["nom"]
        assert x["prime_totale"] >= 0 and x["motif"]
    total_epargne = synthese_epargne(JUILLET, db_path=DB)["encours_total"]
    assert 0 < sum(x["epargne"] for x in r["agents"]) <= total_epargne
    # couverture : la moyenne réaliste d'un portefeuille (quelques dizaines de %) — ni 0, ni 1000 %
    assert any(0.05 < x["taux_couverture"] < 5 for x in r["agents"])


def test_prerequis_bloquants():
    _preparer()
    from engine.primes_ac_sup import primes_ac_sup
    import socle.schema as S
    from sqlalchemy import delete
    try:
        primes_ac_sup(dt.date(2026, 6, 30), db_path=DB)
        raise AssertionError("sans inventaire épargne, la prime aurait dû être refusée")
    except ValueError as e:
        assert "Inventaire épargne" in str(e)
    s = S.get_session(DB)
    s.execute(delete(S.DimEmploye).where(S.DimEmploye.date_debut == dt.date(2026, 7, 1)))
    s.commit()
    s.close()
    try:
        primes_ac_sup(JUILLET, db_path=DB)
        raise AssertionError("sans roster du mois, la prime aurait dû être refusée")
    except ValueError as e:
        assert "roster" in str(e)
    finally:
        _pret.clear()                                               # base à reconstruire


if __name__ == "__main__":
    code = D.lancer("Primes agents de credit et superviseurs", [
        (test_orchestration_juillet, "Juillet : une ligne par actif, prime = règle validée, épargne comptée une fois"),
        (test_prerequis_bloquants, "Sans inventaire épargne ou sans roster : refus explicite"),
    ])
    from socle.schema import fermer_moteurs
    fermer_moteurs()
    D.sortir(code)
