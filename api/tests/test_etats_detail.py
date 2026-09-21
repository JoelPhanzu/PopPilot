"""
Tests du référentiel des états financiers (engine/etats_detail.py).

POURQUOI CE TEST EXISTE : ce module publie une DÉCLARATION BCC. Les façons de
s'y tromper sont toutes silencieuses — un total qui boucle quand même, une ligne
absente qu'on ne remarque pas, une provision ajoutée au lieu d'être déduite.
Quatre invariants ferment ces portes :

  1. Le total général doit être IDENTIQUE à celui du moteur agrégé déjà validé.
     Deux chemins de calcul indépendants sur les mêmes données : un écart
     signale qu'un compte n'est pas placé.
  2. Un préfixe partagé actif/passif se ventile COMPTE PAR COMPTE. Trier sur le
     cumul du préfixe mettait les deux côtés ensemble et faussait le total
     général de 120 290,81 sur mai 2026 — c'est le défaut réel que ce cas garde.
  3. Les lignes de déduction (provisions, amortissements) s'affichent en positif
     et se RETRANCHENT de leur sous-total.
  4. Les lignes à ZÉRO sont publiées. Une ligne attendue par la BCC et absente
     est une anomalie de déclaration, pas une économie de place.

Base SQLite temporaire, balance fabriquée à la main, chiffres vérifiables de tête.

Lancer :  python tests/test_etats_detail.py
"""
import datetime as dt
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import donnees_test as D   # noqa: E402

DB = "socle/test_etats_detail.db"
ARRETE = dt.date(2026, 5, 31)

#  (numéro, libellé, solde_net)  — solde_net = Débit − Crédit (col G − col H).
#  Actif débiteur positif, passif et produits créditeurs négatifs.
BALANCE = [
    # Trésorerie
    ("57100000", "Caisse USD", 240_836.89),
    ("56100000", "Banque A", 900_000.00),      # débiteur → actif
    ("56200000", "Banque B", -62_215.95),      # créditeur → passif (MÊME préfixe)
    # Clientèle actif
    ("32100000", "Crédit court terme", 6_430_800.93),
    ("31100000", "Crédit moyen terme", 3_195_082.51),
    ("39100000", "Créances litigieuses", 1_188_447.22),
    ("38100000", "Provisions dépréciation cl.3", -938_244.42),   # DÉDUCTION
    # Diverses : le préfixe 46 alimente les DEUX côtés à la fois
    ("46100000", "Débiteurs divers", 33_467.11),
    ("46200000", "Créditeurs divers", -55_869.42),
    # Immobilisations
    ("22100000", "Immobilisations corporelles", 1_249_555.55),
    ("28100000", "Amortissements", -761_172.79),                 # DÉDUCTION
    # Passif
    #  L'épargne fait l'équilibre : une balance d'essai a une somme de soldes
    #  NULLE (Σ débits = Σ crédits). Une fixture qui ne boucle pas ferait sortir
    #  le contrôle d'équilibre en anomalie — et on croirait le moteur fautif.
    ("33100000", "Épargne ordinaire", -7_384_329.54),
    ("10100000", "Capital", -2_500_000.00),
    ("11100000", "Réserves", -437_609.72),
    # Résultat : produits créditeurs, charges débitrices
    ("71100000", "Produits clientèle", -1_939_378.59),
    ("65100000", "Charges du personnel", 840_630.22),
]


def _preparer(extra=()):
    from socle.schema import init_db, get_session, fermer_moteurs, FaitBalance

    os.environ.pop("DATABASE_URL", None)      # repli SQLite local
    fermer_moteurs()
    if os.path.exists(DB):
        try:
            os.remove(DB)
        except PermissionError as e:
            raise AssertionError(f"{DB} verrouillé : session non refermée. {e}")
    init_db(DB)

    s = get_session(DB)
    for numero, libelle, solde in list(BALANCE) + list(extra):
        s.add(FaitBalance(date_arrete=ARRETE, date_snapshot=ARRETE,
                          numero_compte=numero, libelle=libelle,
                          solde_net=solde, devise="USD"))
    s.commit()
    s.close()

    import engine.etats_detail as ED
    import engine.etats_financiers as EF
    origine = get_session
    ED.get_session = lambda *a, **k: origine(DB)
    EF.get_session = lambda *a, **k: origine(DB)
    return ED


def _nettoyer():
    from socle.schema import fermer_moteurs
    fermer_moteurs()
    if os.path.exists(DB):
        try:
            os.remove(DB)
        except PermissionError:
            pass


def _ligne(etat, code):
    for l in etat:
        if l["code"] == code:
            return l
    raise AssertionError(f"ligne {code} absente du référentiel")


# ─────────────────────────────────────────────────────────────────────────────
def test_total_identique_a_l_agregat():
    """Deux chemins de calcul, mêmes données : le total doit être le même."""
    ED = _preparer()
    try:
        r = ED.etats_detailles(ARRETE, db_path=DB)
        c = r["controles"]
        assert abs(c["ecart_avec_agregat"]) < 0.01, \
            f"référentiel et agrégat divergent de {c['ecart_avec_agregat']:,.2f}"
        assert abs(c["ecart_resultat_avec_agregat"]) < 0.01, c
        assert c["nb_comptes_non_places"] == 0, c["comptes_non_places"]
    finally:
        _nettoyer()


def test_prefixe_mixte_ventile_compte_par_compte():
    """(46) et (56) alimentent l'actif ET le passif : c'est le signe de CHAQUE
    compte qui décide, jamais le cumul du préfixe."""
    ED = _preparer()
    try:
        r = ED.etats_detailles(ARRETE, db_path=DB)
        debiteurs = _ligne(r["actif"], "V1.F0a.21")     # (46) Débiteurs divers
        crediteurs = _ligne(r["passif"], "V1.F0p.17")   # (46) Créditeurs divers
        assert abs(debiteurs["montant"] - 33_467.11) < 0.01, debiteurs["montant"]
        assert abs(crediteurs["montant"] - 55_869.42) < 0.01, crediteurs["montant"]
        # Chaque côté ne porte QUE ses comptes.
        assert [c["numero_compte"] for c in debiteurs["comptes"]] == ["46100000"]
        assert [c["numero_compte"] for c in crediteurs["comptes"]] == ["46200000"]

        banque_actif = _ligne(r["actif"], "V1.F0a.04")
        banque_passif = _ligne(r["passif"], "V1.F0p.03")
        assert abs(banque_actif["montant"] - 900_000.00) < 0.01, banque_actif
        assert abs(banque_passif["montant"] - 62_215.95) < 0.01, banque_passif
    finally:
        _nettoyer()


def test_deductions_affichees_positives_et_retranchees():
    """Provisions (38) et amortissements (28) : positifs à l'écran, déduits du total."""
    ED = _preparer()
    try:
        r = ED.etats_detailles(ARRETE, db_path=DB)

        prov = _ligne(r["actif"], "V1.F0a.13")
        amort = _ligne(r["actif"], "V1.F0a.32")
        assert prov["montant"] > 0 and prov["signe"] == -1, prov
        assert amort["montant"] > 0 and amort["signe"] == -1, amort

        # Clientèle = 6 430 800,93 + 3 195 082,51 − 938 244,42 + 1 188 447,22
        clientele = _ligne(r["actif"], "V1.F0a.08")
        attendu = 6_430_800.93 + 3_195_082.51 - 938_244.42 + 1_188_447.22
        assert abs(clientele["montant"] - attendu) < 0.01, clientele["montant"]

        # Immobilisations = 1 249 555,55 − 761 172,79
        immob = _ligne(r["actif"], "V1.F0a.24")
        assert abs(immob["montant"] - (1_249_555.55 - 761_172.79)) < 0.01, immob["montant"]
    finally:
        _nettoyer()


def test_lignes_a_zero_publiees():
    """Le référentiel est publié EN ENTIER : 32 lignes d'actif, 28 de passif, 26 au CR."""
    ED = _preparer()
    try:
        r = ED.etats_detailles(ARRETE, db_path=DB)
        assert len(r["actif"]) == 32, len(r["actif"])
        assert len(r["passif"]) == 28, len(r["passif"])
        assert len(r["resultat"]) == 26, len(r["resultat"])

        # (30) Crédit long terme : aucun compte en base, la ligne existe à zéro.
        vide = _ligne(r["actif"], "V1.F0a.11")
        assert vide["montant"] == 0.0 and vide["comptes"] == [], vide
    finally:
        _nettoyer()


def test_resultat_alimente_le_passif_sans_double_compte():
    """Compte 13 à zéro : le passif prend le résultat CALCULÉ, et le bilan boucle."""
    ED = _preparer()
    try:
        r = ED.etats_detailles(ARRETE, db_path=DB)
        resultat = 1_939_378.59 - 840_630.22
        assert abs(r["resultat_net"] - resultat) < 0.01, r["resultat_net"]

        au_passif = _ligne(r["passif"], "V1.F0p.25")
        assert abs(au_passif["montant"] - resultat) < 0.01, au_passif["montant"]
        assert "classes 6 et 7" in r["resultat_source"], r["resultat_source"]
        assert r["controles"]["equilibre"], r["controles"]["bilan_equilibre_ecart"]
    finally:
        _nettoyer()


def test_resultat_affecte_prime_sur_le_calcul():
    """Compte 13 renseigné (résultat affecté) : on le prend LUI, pas les classes 6-7.

    Additionner les deux compterait le résultat en double et déséquilibrerait le
    bilan d'un montant égal au résultat.
    """
    #  On remplace le résultat calculé par un compte 13 de même montant : le bilan
    #  doit toujours boucler, et la source doit changer.
    ED = _preparer(extra=[("13100000", "Résultat net affecté", -(1_939_378.59 - 840_630.22))])
    try:
        r = ED.etats_detailles(ARRETE, db_path=DB)
        assert "compte 13" in r["resultat_source"], r["resultat_source"]
        au_passif = _ligne(r["passif"], "V1.F0p.25")
        attendu = 1_939_378.59 - 840_630.22
        assert abs(au_passif["montant"] - attendu) < 0.01, au_passif["montant"]
        # Pas de double comptage : une seule fois au passif.
        fp = _ligne(r["passif"], "V1.F0p.23")
        assert abs(fp["montant"] - (2_500_000.00 + 437_609.72 + attendu)) < 0.01, fp["montant"]
    finally:
        _nettoyer()


def test_compte_hors_referentiel_est_nomme():
    """Un compte qu'aucune ligne ne place doit être SIGNALÉ, pas avalé."""
    ED = _preparer(extra=[("99100000", "Compte hors plan", 1_234.56)])
    try:
        r = ED.etats_detailles(ARRETE, db_path=DB)
        c = r["controles"]
        assert c["nb_comptes_non_places"] == 1, c
        assert "99100000" in c["comptes_non_places"], c["comptes_non_places"]
    finally:
        _nettoyer()


def test_soldes_intermediaires_du_compte_de_resultat():
    """80, 82, 83, 84, 85 et 87 s'enchaînent comme dans le référentiel."""
    ED = _preparer()
    try:
        r = ED.etats_detailles(ARRETE, db_path=DB)["resultat"]
        pnf = _ligne(r, "V1.F1.09")["montant"]          # (80)
        rbe = _ligne(r, "V1.F1.14")["montant"]          # (82)
        rce = _ligne(r, "V1.F1.19")["montant"]          # (83)
        avant_impot = _ligne(r, "V1.F1.24")["montant"]  # (85)
        net = _ligne(r, "V1.F1.26")["montant"]          # (87)

        assert abs(pnf - 1_939_378.59) < 0.01, pnf
        assert abs(rbe - (pnf - 840_630.22)) < 0.01, rbe
        assert abs(rce - rbe) < 0.01, rce            # aucune dotation dans ce jeu
        assert abs(avant_impot - rce) < 0.01, avant_impot
        assert abs(net - avant_impot) < 0.01, net    # impôt nul
    finally:
        _nettoyer()


if __name__ == "__main__":
    D.sortir(D.lancer("Referentiel des etats financiers", [
        (test_total_identique_a_l_agregat,
         "total general identique a l'agregat valide"),
        (test_prefixe_mixte_ventile_compte_par_compte,
         "prefixe mixte ventile COMPTE PAR COMPTE (46 et 56 des deux cotes)"),
        (test_deductions_affichees_positives_et_retranchees,
         "provisions et amortissements : affiches positifs, retranches"),
        (test_lignes_a_zero_publiees,
         "referentiel publie en entier, lignes a zero comprises"),
        (test_resultat_alimente_le_passif_sans_double_compte,
         "resultat calcule porte au passif, bilan equilibre"),
        (test_resultat_affecte_prime_sur_le_calcul,
         "compte 13 renseigne : pas de double comptage du resultat"),
        (test_compte_hors_referentiel_est_nomme,
         "compte hors referentiel signale, jamais avale"),
        (test_soldes_intermediaires_du_compte_de_resultat,
         "soldes intermediaires 80/82/83/85/87 s'enchainent"),
    ]))
