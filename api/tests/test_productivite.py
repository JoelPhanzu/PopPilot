"""
Tests : import des remboursements (hiérarchie résolue) + profil de productivité.

POURQUOI : la productivité ventile les intérêts encaissés sur les agents. Un remboursement
perdu ou compté deux fois fausserait la profitabilité d'un agent sans erreur visible ; un
agent absent du roster qui garderait « sa » performance violerait la règle orphelin.

Invariants vérifiés (base SQLite de test, jamais Supabase) :
  - intérêts importés = 344 115,98 (fichier des remboursements d'août) ;
  - rattachés (mois + mois précédent) + non rattachés = total ;
  - Σ lignes = encours de engine.par, décaissements de engine.decaissement, intérêts importés,
    à CHAQUE niveau (agent, superviseur, agence) — orphelins/gelés/non rattachés compris ;
  - roster du mois : présent → performance ; absent → orphelin ; pas de roster → aucun profil ;
  - AGENCE : ne voit que son agence.
NB : l'encours d'août n'est pas en local ; on rattache sur l'encours de JUILLET (mois) et de
MAI (précédent). La répartition diffère d'août réel, les invariants non.

Lancer :  python tests/test_productivite.py
"""
import datetime as dt
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import donnees_test as D   # noqa: E402

DB = "socle/test_productivite.db"
JUILLET, MAI = dt.date(2026, 7, 31), dt.date(2026, 5, 31)
REMB = ("Crédit_remboursés_Aout_2026.xlsx", "Crédit_remboursés_Aout_2026.xlsx",
        "Cr├®dit_rembours├®s_Aout_2026.xlsx")
_etat = {}


def _preparer():
    if _etat:
        return _etat
    import socle.schema as S
    os.environ.pop("DATABASE_URL", None)
    remb = D.exiger_un_de(*REMB)
    enc_juil = D.exiger("Encours_credit_JUILLET_2026.xlsx")
    enc_mai = D.exiger("Enours_MAI_2026_.xls")
    objectif = D.exiger("OBJECTIF.xlsx")
    S.fermer_moteurs()
    if os.path.exists(DB):
        os.remove(DB)
    from socle.seed_parametres import seed
    from ingest.import_credit import importer_credit
    from ingest.import_remboursements import importer_remboursements
    seed(DB)
    importer_credit(enc_mai, MAI, date_snapshot=dt.date(2026, 6, 1), db_path=DB)
    importer_credit(enc_juil, JUILLET, date_snapshot=dt.date(2026, 8, 1), db_path=DB)
    _etat["import"] = importer_remboursements(remb, JUILLET, db_path=DB)
    _etat["objectif"] = objectif
    return _etat


def _profil(niveau):
    from engine.productivite import profil_productivite
    return profil_productivite(JUILLET, niveau, db_path=DB)


def test_import_total_et_cascade():
    r = _preparer()["import"]
    assert r["interets_total"] == 344115.98, r
    assert (r["rattaches_encours_du_mois"] + r["rattaches_encours_precedent"]
            + r["non_rattaches"]) == r["lignes_importees"], r
    assert r["encours_precedent"] == "2026-05-31", r


def test_cascade_mois_puis_precedent():
    """Dossier du mois → mois ; soldé (seulement au mois précédent) → précédent ; inconnu → non rattaché."""
    _preparer()
    import tempfile
    import openpyxl
    from socle.schema import get_session, FaitCredit, FaitRemboursementEncaisse as F
    from ingest.import_remboursements import importer_remboursements
    s = get_session(DB)
    juil = {x for (x,) in s.query(FaitCredit.numero_dossier).filter(FaitCredit.date_arrete == JUILLET)}
    mai = s.query(FaitCredit).filter(FaitCredit.date_arrete == MAI).all()
    s.close()
    solde = next(p for p in mai if p.numero_dossier not in juil)       # soldé entre mai et juillet
    du_mois = sorted(juil)[0]
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Date", "Ech", "Client", "Nom", "Dossier", "Debourse", "Capital", "Interets", "Penalites"])
    ws.append(["15/07/2026", 1, "1", "A", du_mois, 100, 10, 1.5, 0])
    ws.append(["16/07/2026", 1, "2", "B", solde.numero_dossier, 100, 10, 2.5, 0])
    ws.append(["17/07/2026", 1, "3", "C", "999999999", 100, 10, 4, 0])
    chemin = os.path.join(tempfile.mkdtemp(), "remb_test.xlsx")
    wb.save(chemin)
    try:
        r = importer_remboursements(chemin, JUILLET, db_path=DB)
        assert (r["rattaches_encours_du_mois"], r["rattaches_encours_precedent"],
                r["non_rattaches"], r["interets_non_rattaches"], r["dates_hors_du_mois"]) == (1, 1, 1, 4.0, 0), r
        s = get_session(DB)
        l = s.query(F).filter(F.numero_dossier == str(solde.numero_dossier)).one()
        s.close()
        assert (l.agent_credit, l.agence) == (solde.agent_credit, solde.agence)
    finally:
        importer_remboursements(D.exiger_un_de(*REMB), JUILLET, db_path=DB)   # état réel rétabli


def test_import_idempotent():
    _preparer()
    from ingest.import_remboursements import importer_remboursements
    r = importer_remboursements(D.exiger_un_de(*REMB), JUILLET, db_path=DB)
    assert r["remplacees"] == r["lignes_importees"]
    from socle.schema import get_session, FaitRemboursementEncaisse as F
    s = get_session(DB)
    n = s.query(F).filter(F.date_arrete == JUILLET).count()
    s.close()
    assert n == r["lignes_importees"], "le ré-import a dupliqué"


def test_pas_de_roster_pas_de_profil_individuel():
    _preparer()
    for niveau in ("agent", "superviseur"):
        r = _profil(niveau)
        assert r["roster_du_mois"] is False and r["lignes"] == [] and "OBJECTIF" in r["message"]
    assert _profil("agence")["lignes"]                               # l'agence ne dépend pas du roster


def _verifier_invariants(niveau):
    from engine.par import calculer_par
    from engine.decaissement import decaissements
    r = _profil(niveau)
    t = r["totaux"]
    g = calculer_par(JUILLET, db_path=DB)["global"]
    dec = decaissements(JUILLET, db_path=DB)["global"]
    assert abs(t["encours"] - g.encours) < 0.01, (niveau, t["encours"], g.encours)
    assert t["nb_credits"] == g.nb_credits
    assert abs(t["decaisse_volume"] - dec["volume"]) < 0.01 and t["decaisse_nombre"] == dec["nombre"]
    assert abs(t["interets_encaisses"] - 344115.98) < 0.01, (niveau, t["interets_encaisses"])
    return r


def test_invariants_et_regle_orphelin():
    etat = _preparer()
    from ingest.import_objectifs import importer_objectifs
    # Roster de test daté de JUILLET (le fichier OBJECTIF réel est celui de mai).
    importer_objectifs(etat["objectif"], dt.date(2026, 7, 1), db_path=DB)
    from socle.schema import get_session, DimEmploye
    s = get_session(DB)
    au_roster = {(e.nom.strip().upper(), e.agence.strip().upper())
                 for e in s.query(DimEmploye).filter(DimEmploye.date_debut == dt.date(2026, 7, 1),
                                                     DimEmploye.fonction == "agent_credit")}
    s.close()
    agents = _verifier_invariants("agent")
    _verifier_invariants("superviseur")
    agences = _verifier_invariants("agence")
    actifs = [l for l in agents["lignes"] if l["statut"] == "actif"]
    # Un agent actif = au roster, à l'identique ou par son nom court (socle/roster.py :
    # « MUBANGA DJO » au roster = « MUBANGA MUBANGA DJO » au CBS).
    from socle.roster import correspondances, normaliser
    rattaches = correspondances({(normaliser(n), normaliser(a)) for n, a in au_roster},
                                [(l["designation"], l["agence"]) for l in actifs])
    assert actifs and all((normaliser(l["designation"]), normaliser(l["agence"])) in rattaches
                          for l in actifs), "un agent hors roster a gardé sa performance"
    assert (("MUBANGA MUBANGA DJO", "AGENCE DE LUBUMBASHI")
            in rattaches) == any(l["designation"] == "MUBANGA MUBANGA DJO" for l in actifs)
    assert any(l["statut"] == "orphelin" for l in agents["lignes"])
    assert all("effectif_agents" in l for l in agences["lignes"])


def test_cloisonnement_agence():
    _preparer()
    import productivite as P
    import engine.productivite as E
    origine = E.profil_productivite
    P.profil_productivite = lambda d, n: origine(d, n, db_path=DB)
    try:
        r = P.endpoint_productivite(arrete="2026-07-31", niveau="agence",
                                    user={"login": "v", "role": "AGENCE", "agence": "AGENCE DE VICTOIRE"})
        tout = P.endpoint_productivite(arrete="2026-07-31", niveau="agence",
                                       user={"login": "c", "role": "CDG", "agence": None})
    finally:
        P.profil_productivite = origine
    assert {l["agence"] for l in r["lignes"]} == {"AGENCE DE VICTOIRE"}
    v = next(l for l in tout["lignes"] if l["agence"] == "AGENCE DE VICTOIRE")
    assert abs(r["totaux"]["interets_encaisses"] - v["interets_encaisses"]) < 0.01


def test_encaissements_dans_le_tableau_de_bord():
    """Le tableau de bord crédit reprend les intérêts encaissés du fichier au centime, sur la
    période de flux, et Σ agences = MICROPOP (les non rattachés restent sur leur ligne)."""
    _preparer()
    from engine.tableau_de_bord_credit import tableau_de_bord_credit
    r = tableau_de_bord_credit(JUILLET, dt.date(2026, 8, 1), dt.date(2026, 8, 31), db_path=DB)
    g, reste = r["lignes"][0], r["lignes"][1:]
    assert abs(g["interets_encaisses"] - 344115.98) < 0.01, g["interets_encaisses"]
    assert abs(sum(l["interets_encaisses"] for l in reste) - g["interets_encaisses"]) < 0.01
    assert g["nb_remboursements"] == _etat["import"]["lignes_importees"]
    assert 0 < g["recouvre_sur_par"] < g["capital_rembourse"] + g["interets_encaisses"] + g["penalites_encaissees"]
    vide = tableau_de_bord_credit(JUILLET, dt.date(2026, 7, 1), dt.date(2026, 7, 31), db_path=DB)
    assert vide["lignes"][0]["nb_remboursements"] == 0                   # hors période : rien


if __name__ == "__main__":
    code = D.lancer("Productivité (remboursements + profil)", [
        (test_encaissements_dans_le_tableau_de_bord, "Tableau de bord : intérêts encaissés 344 115,98 sur la période"),
        (test_import_total_et_cascade, "Import : 344 115,98 ; mois + précédent + non rattachés = total"),
        (test_cascade_mois_puis_precedent, "Cascade : mois, sinon mois précédent (soldé), sinon non rattaché"),
        (test_import_idempotent, "Import rejouable (remplace, ne duplique pas)"),
        (test_pas_de_roster_pas_de_profil_individuel, "Sans roster du mois : aucun profil agent/superviseur"),
        (test_invariants_et_regle_orphelin, "Σ lignes = encours /par, décaissements, intérêts ; hors roster -> orphelin"),
        (test_cloisonnement_agence, "AGENCE : seulement son agence, totaux = les siens"),
    ])
    from socle.schema import fermer_moteurs
    fermer_moteurs()
    D.sortir(code)
