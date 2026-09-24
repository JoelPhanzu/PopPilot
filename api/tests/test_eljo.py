"""
Tests Eljo Smart (POST /eljo) : la réponse est le chiffre EXACT du moteur, jamais inventé.

Sur l'extraction réelle de mai (base SQLite de test) :
  - « PAR de mai 2026 à Victoire » → PAR30 Victoire du Dashboard (260 281,47) ;
  - « encours de mai 2026 » → 10 814 330,66 ; « provisions de mai 2026 » → 938 244,42 ;
  - mois non importé → « indisponible », pas le mois voisin ;
  - AGENCE : ramenée à son agence, refusée pour une autre, pas de provisions institution ;
  - chaque échange est tracé dans eljo_conversation.

Lancer :  python tests/test_eljo.py
"""
import datetime as dt
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import donnees_test as D   # noqa: E402

DB = "socle/test_eljo.db"
_pret = []


def _eljo():
    import eljo
    if _pret:
        return eljo
    import socle.schema as S
    os.environ.pop("DATABASE_URL", None)
    source = D.exiger("Enours_MAI_2026_.xls")
    S.fermer_moteurs()
    if os.path.exists(DB):
        os.remove(DB)
    from socle.seed_parametres import seed
    from ingest.import_credit import importer_credit
    seed(DB)
    importer_credit(source, dt.date(2026, 5, 30), date_snapshot=dt.date(2026, 6, 1), db_path=DB)
    eljo.BASE = DB
    _pret.append(True)
    return eljo


def _u(role):
    return {"login": role.lower(), "role": role,
            "agence": "AGENCE DE VICTOIRE" if role == "AGENCE" else None}


def _q(texte, role="CDG"):
    E = _eljo()
    return E.endpoint_eljo(E.Question(question=texte), user=_u(role))


def test_par_agence_exact():
    r = _q("Quel est le PAR de mai 2026 à Victoire ?")
    assert abs(r["valeur"] - 260281.47) < 0.01, r
    assert r["detail"]["perimetre"] == "AGENCE DE VICTOIRE" and r["detail"]["arrete"] == "2026-05-30"


def test_encours_et_provisions_institution():
    assert abs(_q("encours de mai 2026")["valeur"] - 10814330.66) < 0.01
    assert abs(_q("provisions de mai 2026")["valeur"] - 938244.42) < 0.01


def test_mois_absent_pas_de_voisin():
    r = _q("encours de juin 2026")
    assert r["valeur"] is None and "indisponible" in r["reponse"].lower(), r


def test_sans_indicateur():
    r = _q("bonjour Eljo")
    assert r["valeur"] is None and "identifié" in r["reponse"]


def test_cloisonnement_agence():
    r = _q("PAR de mai 2026", role="AGENCE")                       # ramenée à Victoire
    assert abs(r["valeur"] - 260281.47) < 0.01, r
    r = _q("PAR de mai 2026 à Ozone", role="AGENCE")
    assert r["valeur"] is None and "uniquement" in r["reponse"], r
    r = _q("provisions de mai 2026", role="AGENCE")
    assert r["valeur"] is None and "réservé" in r["reponse"], r


def test_trace_et_historique():
    E = _eljo()
    avant = len(E.endpoint_historique(limite=200, user=_u("CDG"))["echanges"])
    _q("encours de mai 2026")
    h = E.endpoint_historique(limite=200, user=_u("CDG"))["echanges"]
    assert len(h) == avant + 1 and abs(h[-1]["valeur"] - 10814330.66) < 0.01
    assert h[-1]["intention"] == "encours"
    assert all(e["question"] for e in E.endpoint_historique(limite=200, user=_u("AGENCE"))["echanges"])


if __name__ == "__main__":
    code = D.lancer("Eljo Smart (POST /eljo)", [
        (test_par_agence_exact, "« PAR de mai 2026 à Victoire » = 260 281,47 (Dashboard)"),
        (test_encours_et_provisions_institution, "encours 10 814 330,66 ; provisions 938 244,42"),
        (test_mois_absent_pas_de_voisin, "mois non importé -> indisponible (pas de mois voisin)"),
        (test_sans_indicateur, "question sans indicateur -> aide, aucune valeur"),
        (test_cloisonnement_agence, "AGENCE : sa seule agence ; autre agence et provisions refusées"),
        (test_trace_et_historique, "échange tracé dans eljo_conversation ; historique personnel"),
    ])
    from socle.schema import fermer_moteurs
    fermer_moteurs()
    D.sortir(code)
