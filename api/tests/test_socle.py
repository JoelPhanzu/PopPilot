"""
Tests Phase 0 — le socle tient debout : schéma, idempotence, résolution de snapshot,
distinction date_arrete/date_snapshot, calendrier ouvré.
Lancer : python -m pytest tests/ -v   (ou python tests/test_socle.py)
"""
import datetime as dt
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from socle.schema import init_db, get_session, FaitCredit, Base
from socle import historisation as H
from socle.seed_parametres import seed

DB = "socle/test_micropop.db"


def _fresh():
    if os.path.exists(DB):
        os.remove(DB)
    init_db(DB)
    return get_session(DB)


def test_schema_cree_toutes_les_tables():
    s = _fresh()
    assert len(Base.metadata.tables) == 28
    s.close()


def test_idempotence_reimport_remplace():
    """Ré-importer la même date_arrete ne crée pas de doublon (règle I-4)."""
    s = _fresh()
    arrete = dt.date(2026, 4, 30)
    # 1er import : 2 prêts
    for i in (1, 2):
        s.add(FaitCredit(date_arrete=arrete, date_snapshot=dt.date(2026, 5, 4),
                         numero_dossier=str(i), encours=100.0 * i, jours_de_retard=0))
    s.commit()
    assert s.query(FaitCredit).filter_by(date_arrete=arrete).count() == 2
    # ré-import : purge puis 3 prêts
    purges = H.purge_snapshot(s, "credit", arrete)
    assert purges == 2
    for i in (1, 2, 3):
        s.add(FaitCredit(date_arrete=arrete, date_snapshot=dt.date(2026, 5, 6),
                         numero_dossier=str(i), encours=50.0, jours_de_retard=0))
    s.commit()
    assert s.query(FaitCredit).filter_by(date_arrete=arrete).count() == 3
    s.close()


def test_date_arrete_distincte_de_snapshot():
    """Un import du 4 mai portant l'arrêté du 30 avril est rangé en AVRIL (§69.2)."""
    s = _fresh()
    s.add(FaitCredit(date_arrete=dt.date(2026, 4, 30), date_snapshot=dt.date(2026, 5, 4),
                     numero_dossier="X", encours=10.0, jours_de_retard=0))
    s.commit()
    row = s.query(FaitCredit).one()
    assert row.date_arrete.month == 4      # comptable = avril
    assert row.date_snapshot.month == 5    # import = mai
    s.close()


def test_snapshot_le_plus_recent_sans_interpolation():
    """Demander le 20 mai alors qu'on n'a que le 30 avril → renvoie 30 avril, exact=False (§20.2)."""
    s = _fresh()
    s.add(FaitCredit(date_arrete=dt.date(2026, 4, 30), date_snapshot=dt.date(2026, 5, 4),
                     numero_dossier="X", encours=10.0, jours_de_retard=0))
    s.commit()
    d, exact = H.snapshot_le_plus_recent(s, "credit", dt.date(2026, 5, 20))
    assert d == dt.date(2026, 4, 30)
    assert exact is False
    # pile sur la date → exact
    d2, exact2 = H.snapshot_le_plus_recent(s, "credit", dt.date(2026, 4, 30))
    assert exact2 is True
    # aucune donnée antérieure
    d3, exact3 = H.snapshot_le_plus_recent(s, "credit", dt.date(2026, 1, 1))
    assert d3 is None and exact3 is False
    s.close()


def test_calendrier_defaut_samedi_ouvre():
    """Défaut : samedi ouvré, dimanche non. 30 mai 2026 = samedi → dernier jour ouvré de mai."""
    s = _fresh()
    assert H.est_jour_ouvre(s, dt.date(2026, 5, 31)) is False   # dimanche
    assert H.est_jour_ouvre(s, dt.date(2026, 5, 30)) is True    # samedi = ouvré
    assert H.dernier_jour_ouvre_du_mois(s, 2026, 5) == dt.date(2026, 5, 30)
    s.close()


def test_ferie_recurrent_rdc():
    """Les fériés fixes RDC sont non ouvrés sans aucune saisie (ex. 30 juin, Indépendance)."""
    from socle import calendrier as C
    s = _fresh()
    assert H.est_jour_ouvre(s, dt.date(2026, 6, 30)) is False   # Indépendance
    assert H.est_jour_ouvre(s, dt.date(2026, 1, 1)) is False    # Nouvel An
    assert H.est_jour_ouvre(s, dt.date(2026, 5, 17)) is False   # Révolution/FA
    # 30 juin 2026 = mardi, férié → dernier jour ouvré de juin = lundi 29
    assert dt.date(2026, 6, 30).weekday() == 1
    assert H.dernier_jour_ouvre_du_mois(s, 2026, 6) == dt.date(2026, 6, 29)
    s.close()


def test_report_ferie_weekend():
    """Férié tombant un dimanche, reporté au lundi par arrêté → le lundi devient chômé."""
    from socle import calendrier as C
    s = _fresh()
    # 17 mai 2026 = dimanche (Révolution) ; suggéré au report
    assert dt.date(2026, 5, 17).weekday() == 6
    sugg = C.suggerer_reports(s, 2026)
    assert any(d == dt.date(2026, 5, 17) for d, _, _ in sugg)
    # l'admin acte le report au lundi 18
    C.reporter_ferie(s, dt.date(2026, 5, 17), dt.date(2026, 5, 18))
    assert H.est_jour_ouvre(s, dt.date(2026, 5, 18)) is False   # lundi désormais chômé
    s.close()


def test_jour_exceptionnel():
    """Journée non ouvrée exceptionnelle (deuil, salubrité) saisie à la main."""
    from socle import calendrier as C
    s = _fresh()
    jour = dt.date(2026, 3, 12)                                 # jeudi normal
    assert H.est_jour_ouvre(s, jour) is True
    C.declarer_exception(s, jour, est_ouvre=False, libelle="Journée de salubrité")
    assert H.est_jour_ouvre(s, jour) is False
    # inversement : un dimanche exceptionnellement travaillé
    dim = dt.date(2026, 3, 15)
    C.declarer_exception(s, dim, est_ouvre=True, libelle="Inventaire exceptionnel")
    assert H.est_jour_ouvre(s, dim) is True
    s.close()


def test_seed_parametres():
    if os.path.exists(DB):
        os.remove(DB)
    seed(DB)
    s = get_session(DB)
    from socle.schema import ParamBaremeProvision, ParamBaremePrime
    assert s.query(ParamBaremeProvision).count() == 7
    assert s.query(ParamBaremePrime).count() == 4
    # tranche PAR 31-60 = 25 %
    t = s.query(ParamBaremeProvision).filter_by(code=2).one()
    assert t.taux == 0.25
    s.close()


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"  ✓ {name}")
    print("Tous les tests Phase 0 passent.")
