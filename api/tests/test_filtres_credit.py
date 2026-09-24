"""
Tests du tableau de bord crédit FILTRÉ (GET /credit/filtre) — api/filtres_credit.py.

POURQUOI : le filtre s'intercale AVANT les moteurs PAR et provisions. S'il perdait ou
dupliquait un prêt, tous les chiffres filtrés seraient faux sans erreur visible. On vérifie
donc, sur l'extraction RÉELLE de mai :
  - sans filtre  → exactement le Dashboard (et /provisions : 938 244,42) ;
  - filtre agence → exactement la ligne agence du Dashboard ;
  - partitions (sexe, durée) → la somme des morceaux redonne le total, au centime ;
  - cloisonnement : un rôle AGENCE ne sort jamais de son agence ;
  - complément manuel DAF : inclus sur agences entières, exclu (et signalé) sous l'agence.

Lancer :  python tests/test_filtres_credit.py
"""
import datetime as dt
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import donnees_test as D   # noqa: E402

DB = "socle/test_filtres.db"
ARRETE = "2026-05-30"
NOM_EXTRACTION = "Enours_MAI_2026_.xls"

# Dashboard DailyToolReporting_Mai (encours, PAR1, PAR30, PAR90) — cf. test_phase1_par.
REF_MICROPOP = (10814330.66, 1188447.22, 1052118.05, 935909.77)
REF_VICTOIRE = (2531178.47, 274877.29, 260281.47, 238210.18)
REF_PROVISIONS = 938244.42

_pret = False


def _preparer():
    """Base SQLite de test chargée UNE fois (import de ~8 000 prêts)."""
    global _pret
    D.exiger(NOM_EXTRACTION)
    from socle.schema import get_session, fermer_moteurs
    os.environ.pop("DATABASE_URL", None)
    import filtres_credit as F
    origine = get_session
    F.get_session = lambda *a, **k: origine(DB)
    if _pret:
        return F
    from socle.seed_parametres import seed
    from ingest.import_credit import importer_credit
    fermer_moteurs()
    if os.path.exists(DB):
        os.remove(DB)
    seed(DB)
    importer_credit(D.fichier(NOM_EXTRACTION), dt.date(2026, 5, 30),
                    date_snapshot=dt.date(2026, 6, 1), db_path=DB)
    _pret = True
    return F


def _u(role):
    return {"login": role.lower(), "role": role,
            "agence": "AGENCE DE VICTOIRE" if role == "AGENCE" else None}


def _appel(F, user=None, **filtres):
    base = dict(agence=None, sexe=None, produits=None, duree=None, client=None,
                agent=None, superviseur=None)
    base.update(filtres)
    return F.endpoint_credit_filtre(arrete=ARRETE, user=user or _u("CDG"), **base)


def _egal(g, ref, quoi):
    for cle, v in zip(("encours", "par1", "par30", "par90"), ref):
        assert abs(g[cle] - v) < 0.01, f"{quoi} {cle} {g[cle]:,.2f} != {v:,.2f}"


# ─────────────────────────────────────────────────────────────────────────────
def test_sans_filtre_egale_dashboard_et_provisions():
    F = _preparer()
    r = _appel(F)
    _egal(r["global"], REF_MICROPOP, "MICROPOP")
    assert abs(r["provisions"]["total"] - REF_PROVISIONS) < 0.01, r["provisions"]
    assert r["filtres"] == {} and r["portee"] == "MICROPOP"


def test_filtre_agence_egale_ligne_dashboard():
    F = _preparer()
    r = _appel(F, agence="AGENCE DE VICTOIRE")
    _egal(r["global"], REF_VICTOIRE, "VICTOIRE")
    assert [a["agence"] for a in r["agences"]] == ["AGENCE DE VICTOIRE"]


def _partition(F, cle, valeurs):
    total = _appel(F)
    morceaux = [_appel(F, **{cle: v}) for v in valeurs]
    for champ in ("encours", "par1", "par30", "par90"):
        somme = sum(m["global"][champ] for m in morceaux)
        assert abs(somme - total["global"][champ]) < 0.01, \
            f"{cle} : Σ {champ} {somme:,.2f} != total {total['global'][champ]:,.2f}"
    assert sum(m["nb_prets_selectionnes"] for m in morceaux) == total["nb_prets_selectionnes"]
    return morceaux


def test_partition_duree_redonne_le_total():
    F = _preparer()
    _partition(F, "duree", ["court", "moyen", "long"])


def test_partition_sexe_redonne_le_total():
    F = _preparer()
    from socle.schema import get_session, FaitCredit
    from sqlalchemy import select
    s = get_session(DB)
    sexes = {(x or "").upper() for x in s.execute(select(FaitCredit.sexe).where(
        FaitCredit.date_arrete == dt.date(2026, 5, 30))).scalars()}
    s.close()
    assert sexes <= {"F", "H"}, f"valeurs de sexe hors F/H dans l'extraction : {sexes}"
    _partition(F, "sexe", ["F", "H"])


def test_filtre_produit_et_client():
    F = _preparer()
    v = F.endpoint_valeurs_filtres(arrete=ARRETE, user=_u("CDG"))
    assert len(v["agences"]) >= 6 and v["produits"], v
    _partition(F, "produits", [[p] for p in v["produits"]])
    # multi-sélection = somme des produits pris un à un
    deux = v["produits"][:2]
    r = _appel(F, produits=deux)
    un_a_un = sum(_appel(F, produits=[p])["global"]["encours"] for p in deux)
    assert abs(r["global"]["encours"] - un_a_un) < 0.01


def test_agence_cloisonnee():
    F = _preparer()
    from fastapi import HTTPException
    r = _appel(F, user=_u("AGENCE"))                 # aucune agence demandée → la sienne
    _egal(r["global"], REF_VICTOIRE, "AGENCE sans filtre")
    assert r["portee"] == "AGENCE DE VICTOIRE"
    try:
        _appel(F, user=_u("AGENCE"), agence="AGENCE OZONE")
        raise AssertionError("une agence a lu une autre agence")
    except HTTPException as e:
        assert e.status_code == 403
    v = F.endpoint_valeurs_filtres(arrete=ARRETE, user=_u("AGENCE"))
    assert v["agences"] == ["AGENCE DE VICTOIRE"], v["agences"]


def test_complement_manuel_daf():
    F = _preparer()
    from socle.schema import get_session, ProvisionManuelle
    s = get_session(DB)
    s.add(ProvisionManuelle(date_arrete=dt.date(2026, 5, 30), agence="AGENCE DE GOMA",
                            montant=1000.0, note="test", saisi_par="test",
                            horodatage=dt.datetime.now()))
    s.commit(); s.close()
    try:
        r = _appel(F)
        assert abs(r["provisions"]["total"] - (REF_PROVISIONS + 1000)) < 0.01
        # même total que le moteur /provisions
        from engine.derivation import deriver_provisions
        assert abs(deriver_provisions(dt.date(2026, 5, 30), db_path=DB)
                   ["provision_capital_totale"] - r["provisions"]["total"]) < 0.01
        r = _appel(F, sexe="F")
        assert r["provisions"]["complement_manuel_inclus"] is False
        assert r["provisions"]["complement_manuel"] == 0
        assert r["provisions"]["complements_exclus"] == ["AGENCE DE GOMA"]
        r = _appel(F, agence="AGENCE OZONE")
        assert r["provisions"]["complement_manuel"] == 0 and not r["provisions"]["complements_exclus"]
    finally:
        s = get_session(DB)
        s.query(ProvisionManuelle).delete(); s.commit(); s.close()


def test_parametres_invalides():
    F = _preparer()
    from fastapi import HTTPException
    for kw in ({"duree": "tres_long"}, {"sexe": "X"}):
        try:
            _appel(F, **kw)
            raise AssertionError(f"{kw} accepté")
        except HTTPException as e:
            assert e.status_code == 422


if __name__ == "__main__":
    D.sortir(D.lancer("Credit filtre (GET /credit/filtre)", [
        (test_sans_filtre_egale_dashboard_et_provisions,
         "sans filtre = Dashboard mai + provisions 938 244,42"),
        (test_filtre_agence_egale_ligne_dashboard, "filtre agence = ligne VICTOIRE du Dashboard"),
        (test_partition_duree_redonne_le_total, "court + moyen + long = total"),
        (test_partition_sexe_redonne_le_total, "F + H = total"),
        (test_filtre_produit_et_client, "Σ produits = total ; multi-sélection"),
        (test_agence_cloisonnee, "AGENCE forcée sur son agence, autre agence -> 403"),
        (test_complement_manuel_daf, "complément DAF : inclus sur agence entière, exclu sinon"),
        (test_parametres_invalides, "durée / sexe inconnus -> 422"),
    ]))
