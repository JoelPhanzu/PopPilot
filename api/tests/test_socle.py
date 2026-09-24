"""
Tests Phase 0 — le socle tient debout : schéma, idempotence, résolution de snapshot,
distinction date_arrete/date_snapshot, calendrier ouvré.
Lancer : python -m pytest tests/ -v   (ou python tests/test_socle.py)
"""
import datetime as dt
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from socle.schema import init_db, get_session, fermer_moteurs, FaitCredit, Base
from socle import historisation as H
from socle.seed_parametres import seed

DB = "socle/test_micropop.db"


def _fresh():
    # Fermer les pools avant d'effacer le fichier : sous Windows, un moteur SQLite
    # encore ouvert verrouille le .db et os.remove lève PermissionError (WinError 32).
    fermer_moteurs()
    if os.path.exists(DB):
        os.remove(DB)
    init_db(DB)
    return get_session(DB)


def test_schema_cree_toutes_les_tables():
    """Le modèle ORM doit correspondre EXACTEMENT au schéma déployé sur Supabase.

    On ne compte pas les tables (un nombre en dur se périme à chaque ajout, et c'est
    ce qui était arrivé : 28 attendu pour 30 réelles). On compare le jeu de tables du
    modèle à celui de TOUS les scripts supabase/*.sql (01_schema, puis les ajouts
    additifs 06, 07… en « CREATE TABLE IF NOT EXISTS ») — c'est la dérive ORM/base qui
    fait mal : une colonne ou une table présente d'un seul côté casse l'API en silence.
    """
    s = _fresh()
    dossier = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "..", "supabase")
    orm = set(Base.metadata.tables)
    assert orm, "aucune table dans le modèle ORM"

    if os.path.isdir(dossier):
        import glob
        import re
        deployees = set()
        for sql in sorted(glob.glob(os.path.join(dossier, "*.sql"))):
            deployees |= set(re.findall(r"CREATE TABLE (?:IF NOT EXISTS )?(\w+)",
                                        open(sql, encoding="utf-8").read()))
        assert orm == deployees, (
            f"dérive ORM/Supabase — seulement dans l'ORM : {sorted(orm - deployees)} ; "
            f"seulement dans le SQL : {sorted(deployees - orm)}")
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
    fermer_moteurs()                      # libérer le fichier SQLite (Windows)
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


def test_fermer_agence_preserve_le_referentiel():
    """Fermer une agence ne doit RIEN effacer d'autre que son statut.

    `enregistrer_agence` était un upsert intégral : comme `fermer_agence` ne passe que
    statut/date/motif, fermer Goma effaçait son nom, sa région et sa date d'ouverture
    (« Goma | Nord-Kivu | 2015-03-01 » -> « AGENCE DE GOMA | None | None »). Le
    portefeuille d'une agence fermée reste déclarable à la BCC : perdre son référentiel
    au moment où on la ferme est le pire moment.
    """
    from socle.schema import DimAgence
    from socle import agences as A
    s = _fresh()
    A.enregistrer_agence(s, "AGENCE DE GOMA", nom="Goma", region="Nord-Kivu",
                         date_ouverture=dt.date(2015, 3, 1))

    A.fermer_agence(s, "AGENCE DE GOMA", dt.date(2025, 1, 1), motif="Occupation M23")
    a = s.query(DimAgence).filter_by(code_agence="AGENCE DE GOMA").one()
    assert a.statut == "FERMEE" and a.date_fermeture == dt.date(2025, 1, 1)
    assert a.nom == "Goma", f"nom efface par la fermeture : {a.nom!r}"
    assert a.region == "Nord-Kivu", f"region effacee par la fermeture : {a.region!r}"
    assert a.date_ouverture == dt.date(2015, 3, 1), "date d'ouverture effacee"
    assert "AGENCE DE GOMA" in A.agences_fermees(s)

    # Réouverture : le statut revient, le référentiel tient, la date de fermeture part.
    A.rouvrir_agence(s, "AGENCE DE GOMA")
    a = s.query(DimAgence).filter_by(code_agence="AGENCE DE GOMA").one()
    assert (a.statut, a.date_fermeture, a.motif) == ("ACTIVE", None, None)
    assert (a.nom, a.region, a.date_ouverture) == ("Goma", "Nord-Kivu", dt.date(2015, 3, 1))

    # Rouvrir une agence inexistante ne doit rien créer.
    assert A.rouvrir_agence(s, "AGENCE FANTOME") is None
    assert s.query(DimAgence).filter_by(code_agence="AGENCE FANTOME").count() == 0
    s.close()


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"  ✓ {name}")
    fermer_moteurs()
    if os.path.exists(DB):
        os.remove(DB)                     # ne pas laisser de base de test derrière soi
    print("Tous les tests Phase 0 passent.")
