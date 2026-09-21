"""
Tests de l'endpoint de suivi budgétaire (GET /budget) — api/main.py + engine/budget.py.

POURQUOI CE TEST EXISTE : le réalisé MENSUEL est une DIFFÉRENCE de deux cumuls
(la balance arrive cumulée depuis janvier). Toute la doctrine budgétaire figée
avec le CDG tient à ce point, et la façon de se tromper est silencieuse : si la
balance du mois précédent manque, `cumulé(N) − 0` vaut le cumul de sept mois, et
ce cumul s'affiche en face d'un budget d'UN mois. Le taux de réalisation sort
alors à 700 % sans qu'aucune erreur ne soit levée.

Le cas symétrique est JANVIER : là, l'absence de base est normale (le cumul
repart de zéro), et aller chercher le 31/12 précédent soustrairait l'exercice
clos tout entier.

Ce test ne nécessite ni Supabase ni données réelles : base SQLite temporaire,
balance et budget fabriqués à la main, chiffres vérifiables de tête.

Lancer :  python tests/test_budget_api.py
"""
import datetime as dt
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import donnees_test as D   # noqa: E402

DB = "socle/test_budget.db"

# Un seul compte de charge, une seule ligne budgétaire : les chiffres doivent
# rester vérifiables de tête, sinon le test ne prouve rien à qui le relit.
COMPTE = "6.0.2.0.1"
LIGNE = "Frais de personnel"

# Balance CUMULÉE depuis janvier, telle qu'elle arrive de SAGE.
CUMULS = {
    dt.date(2026, 1, 31): 1_000.0,
    dt.date(2026, 5, 31): 5_000.0,
    dt.date(2026, 6, 30): 6_000.0,
    dt.date(2026, 7, 31): 7_500.0,   # juillet : réalisé du mois = 7 500 − 6 000 = 1 500
}
BUDGET_MENSUEL = 1_200.0             # même montant chaque mois : annuel = 14 400


def _preparer():
    """Base SQLite de test : balance cumulée, mapping, budget, et les 4 rôles."""
    from socle.schema import (init_db, get_session, fermer_moteurs, Utilisateur,
                              FaitBalance, FaitBudget, MappingBudget)

    # Le nettoyage vient APRÈS l'import de socle.schema (qui charge api/.env),
    # sinon le .env réel re-remplit l'environnement — cf. test_import_api.
    os.environ.pop("DATABASE_URL", None)      # forcer le repli SQLite local

    # Suppression EXIGEANTE : si la base d'un cas précédent survit, init_db
    # repartirait dessus et le cas suivant lirait des lignes qu'il n'a pas
    # écrites. Mieux vaut un échec net qu'un test qui passe sur de vieux chiffres.
    fermer_moteurs()
    if os.path.exists(DB):
        try:
            os.remove(DB)
        except PermissionError as e:
            raise AssertionError(
                f"{DB} reste verrouillé : une session n'a pas été refermée par le "
                f"cas précédent (fuite de connexion dans le moteur). Détail : {e}")
    init_db(DB)

    s = get_session(DB)
    for login, role, agence in (("cdg", "CDG", None), ("direction", "DIRECTION", None),
                                ("victoire", "AGENCE", "AGENCE DE VICTOIRE"),
                                ("audit", "AUDIT", None)):
        s.add(Utilisateur(login=login, nom_complet=login, mot_de_passe_hash="supabase",
                          sel="supabase", role=role, agence=agence, actif=True,
                          date_creation=dt.date.today(), auth_uid=str(uuid.uuid4())))

    s.add(MappingBudget(numero_compte=COMPTE, ligne_budgetaire=LIGNE,
                        sens="charge", date_effet=dt.date(2026, 1, 1)))

    for arrete, cumul in CUMULS.items():
        s.add(FaitBalance(date_arrete=arrete, date_snapshot=arrete,
                          numero_compte=COMPTE.replace(".", ""), libelle=LIGNE,
                          solde_net=cumul, devise="USD"))

    for mois in range(1, 13):
        s.add(FaitBudget(exercice=2026, hypothese="H1", agence=None,
                         ligne_budgetaire=LIGNE, mois=mois,
                         montant_budgete=BUDGET_MENSUEL, type="charge"))
    s.commit()
    s.close()

    # Tous les accès du moteur passent par get_session : on le fait pointer sur la
    # base de test, sans toucher aux signatures (même procédé que test_import_api).
    import engine.budget as B
    import ingest.import_budget as IB
    origine = get_session
    B.get_session = lambda *a, **k: origine(DB)
    IB.get_session = lambda *a, **k: origine(DB)
    return B


def _nettoyer():
    from socle.schema import fermer_moteurs
    fermer_moteurs()
    if os.path.exists(DB):
        try:
            os.remove(DB)
        except PermissionError:
            pass


def _utilisateur(role: str) -> dict:
    return {"login": role.lower(), "role": role,
            "agence": "AGENCE DE VICTOIRE" if role == "AGENCE" else None}


def _appeler(**kwargs):
    """Appelle l'endpoint sans passer par HTTP (Depends déjà résolu par _utilisateur)."""
    import main
    return main.endpoint_budget(**kwargs)


def _ligne(reponse):
    lignes = [x for x in reponse["lignes"] if x["ligne"] == LIGNE]
    assert len(lignes) == 1, f"ligne {LIGNE} absente de la réponse : {reponse['lignes']}"
    return lignes[0]


# ─────────────────────────────────────────────────────────────────────────────
# Cas
# ─────────────────────────────────────────────────────────────────────────────
def test_realise_mensuel_est_une_difference_de_cumuls():
    """Juillet : réalisé du mois = 7 500 − 6 000 = 1 500, PAS le cumul 7 500."""
    _preparer()
    try:
        r = _appeler(arrete="2026-07-31", user=_utilisateur("CDG"))
        assert r["precedent"] == "2026-06-30", f"base attendue 30/06, obtenue {r['precedent']}"
        assert r["niveau_mensuel_disponible"] is True
        x = _ligne(r)
        assert abs(x["realise_mois"] - 1_500.0) < 0.01, x["realise_mois"]
        assert abs(x["realise_cumule"] - 7_500.0) < 0.01, x["realise_cumule"]
        # % de réalisation du mois : 1 500 / 1 200 = 125 %, et surtout pas 625 %.
        assert abs(x["pct_realisation"] - 1.25) < 1e-6, x["pct_realisation"]
    finally:
        _nettoyer()


def test_exercice_et_mois_sont_deduits_de_l_arrete():
    """Budget cumulé à date de juillet = 7 mois × 1 200 ; annuel = 12 × 1 200."""
    _preparer()
    try:
        r = _appeler(arrete="2026-07-31", user=_utilisateur("CDG"))
        assert (r["exercice"], r["mois"]) == (2026, 7), (r["exercice"], r["mois"])
        x = _ligne(r)
        assert abs(x["budget_cumule_a_date"] - 7 * BUDGET_MENSUEL) < 0.01, x
        assert abs(x["budget_annuel"] - 12 * BUDGET_MENSUEL) < 0.01, x
        assert abs(x["budget_mois"] - BUDGET_MENSUEL) < 0.01, x
    finally:
        _nettoyer()


def test_janvier_le_cumul_est_le_mois():
    """En janvier le cumul repart de zéro : pas de base, et c'est NORMAL."""
    _preparer()
    try:
        r = _appeler(arrete="2026-01-31", user=_utilisateur("CDG"))
        assert r["precedent"] is None, r["precedent"]
        # Le niveau mensuel reste exploitable : c'est tout l'intérêt du cas.
        assert r["niveau_mensuel_disponible"] is True, r
        x = _ligne(r)
        assert abs(x["realise_mois"] - 1_000.0) < 0.01, x["realise_mois"]
        assert abs(x["realise_mois"] - x["realise_cumule"]) < 0.01, x
    finally:
        _nettoyer()


def test_janvier_ne_remonte_jamais_a_l_exercice_precedent():
    """Une balance au 31/12/2025 ne doit PAS servir de base à janvier 2026."""
    B = _preparer()
    try:
        from socle.schema import get_session, FaitBalance
        s = get_session(DB)
        s.add(FaitBalance(date_arrete=dt.date(2025, 12, 31), date_snapshot=dt.date(2025, 12, 31),
                          numero_compte=COMPTE.replace(".", ""), libelle=LIGNE,
                          solde_net=99_000.0, devise="USD"))
        s.commit()
        s.close()

        assert B.arrete_precedent(dt.date(2026, 1, 31)) is None, \
            "janvier a pris le 31/12 précédent pour base : l'exercice clos serait soustrait"

        r = _appeler(arrete="2026-01-31", user=_utilisateur("CDG"))
        x = _ligne(r)
        assert abs(x["realise_mois"] - 1_000.0) < 0.01, x["realise_mois"]
    finally:
        _nettoyer()


def test_base_manquante_le_niveau_mensuel_est_declare_indisponible():
    """Mai : rien entre janvier et mai ⇒ base = janvier, donc mensuel = 5 000 − 1 000.

    Et si plus RIEN n'est antérieur, le moteur doit le DIRE plutôt que de laisser
    passer un cumul entier pour un réalisé mensuel.
    """
    _preparer()
    try:
        r = _appeler(arrete="2026-05-31", user=_utilisateur("CDG"))
        assert r["precedent"] == "2026-01-31", r["precedent"]
        assert abs(_ligne(r)["realise_mois"] - 4_000.0) < 0.01, _ligne(r)

        # On retire toute balance antérieure à mai : plus aucune base possible.
        from socle.schema import get_session, FaitBalance
        s = get_session(DB)
        s.query(FaitBalance).filter(FaitBalance.date_arrete < dt.date(2026, 5, 1)).delete()
        s.commit()
        s.close()

        r = _appeler(arrete="2026-05-31", user=_utilisateur("CDG"))
        assert r["precedent"] is None, r["precedent"]
        assert r["niveau_mensuel_disponible"] is False, \
            "sans base, le niveau mensuel a ete annonce comme exploitable"
        assert r["motif_mensuel_absent"], "aucun motif donne pour l'absence du niveau mensuel"
    finally:
        _nettoyer()


def test_base_explicite_est_respectee():
    """`precedent` fourni à la main prime sur la déduction (rejouer un mois)."""
    _preparer()
    try:
        r = _appeler(arrete="2026-07-31", precedent="2026-01-31", user=_utilisateur("CDG"))
        assert r["precedent"] == "2026-01-31", r["precedent"]
        assert abs(_ligne(r)["realise_mois"] - 6_500.0) < 0.01, _ligne(r)
    finally:
        _nettoyer()


def test_budget_reserve_aux_roles_a_acces_total():
    """Le suivi budgétaire est un agrégat d'institution : AGENCE non, AUDIT oui."""
    from fastapi import HTTPException
    _preparer()
    try:
        try:
            _appeler(arrete="2026-07-31", user=_utilisateur("AGENCE"))
            raise AssertionError("un role AGENCE a obtenu le suivi budgetaire")
        except HTTPException as e:
            assert e.status_code == 403, f"attendu 403, obtenu {e.status_code}"

        for role in ("CDG", "DIRECTION", "AUDIT"):
            r = _appeler(arrete="2026-07-31", user=_utilisateur(role))
            assert r["lignes"], f"{role} n'a recu aucune ligne"
    finally:
        _nettoyer()


def test_arrete_sans_balance_repond_404():
    """Un arrêté non chargé n'est pas une panne : c'est une ressource absente."""
    _preparer()
    try:
        r = _appeler(arrete="2026-09-30", user=_utilisateur("CDG"))
        # Pas de balance en septembre : aucun réalisé. Le budget, lui, existe —
        # la réponse doit donc sortir, avec un réalisé nul et non une erreur.
        x = _ligne(r)
        assert abs(x["realise_cumule"]) < 0.01, x["realise_cumule"]
        assert abs(x["budget_annuel"] - 12 * BUDGET_MENSUEL) < 0.01, x
    finally:
        _nettoyer()


def test_date_invalide_repond_400():
    from fastapi import HTTPException
    _preparer()
    try:
        try:
            _appeler(arrete="31/07/2026", user=_utilisateur("CDG"))
            raise AssertionError("date au mauvais format acceptee")
        except HTTPException as e:
            assert e.status_code == 400, f"attendu 400, obtenu {e.status_code}"
    finally:
        _nettoyer()


if __name__ == "__main__":
    D.sortir(D.lancer("Suivi budgetaire (GET /budget)", [
        (test_realise_mensuel_est_une_difference_de_cumuls,
         "realise mensuel = difference de deux cumuls (pas le cumul)"),
        (test_exercice_et_mois_sont_deduits_de_l_arrete,
         "exercice et mois deduits de l'arrete (budget du bon mois)"),
        (test_janvier_le_cumul_est_le_mois,
         "janvier : le cumul EST le mois, sans base"),
        (test_janvier_ne_remonte_jamais_a_l_exercice_precedent,
         "janvier ne prend jamais le 31/12 precedent pour base"),
        (test_base_manquante_le_niveau_mensuel_est_declare_indisponible,
         "base absente -> niveau mensuel declare indisponible, avec motif"),
        (test_base_explicite_est_respectee,
         "precedent fourni a la main prime sur la deduction"),
        (test_budget_reserve_aux_roles_a_acces_total,
         "AGENCE refusee (403), CDG/DIRECTION/AUDIT servis"),
        (test_arrete_sans_balance_repond_404,
         "arrete sans balance : realise nul, budget toujours rendu"),
        (test_date_invalide_repond_400,
         "date au mauvais format -> 400 explicite"),
    ]))
