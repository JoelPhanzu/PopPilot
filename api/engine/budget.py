"""
Moteur d'analyse budgétaire (Rapport 4) — CLAUDE.md §46-50, §61.

PRINCIPES FIGÉS (CDG) :
- La plateforme s'en tient à la BALANCE, sans retraitement (intégrité des données).
- La balance arrive en CUMULÉ (depuis janvier).
- Réalisé MENSUEL = cumulé(N) − cumulé(N-1) → se compare au BUDGET DU MOIS → % de réalisation.
- Réalisé CUMULÉ = cumulé depuis janvier (balance telle quelle) → se compare au BUDGET ANNUEL TOTAL
  → % de progression.
Mapping compte→ligne : table dynamique mapping_budget (charges + produits).
"""
from __future__ import annotations
import datetime as dt
from collections import defaultdict
from sqlalchemy import select, func
from socle.schema import FaitBalance, FaitBudget, get_session
from engine.etats_financiers import soldes_balance
from ingest.import_budget import lire_mapping


def realise_cumule_par_ligne(date_arrete, db_path="socle/micropop.db", devise="USD"):
    """Réalisé CUMULÉ (depuis janvier) par ligne budgétaire, depuis la balance à cette date.
    Devise explicite : le budget se suit en USD, jamais sur la balance CDF du FINA."""
    if date_arrete is None:
        return {}
    mapping = lire_mapping(db_path=db_path)
    s = get_session(db_path)
    # try/finally : `soldes_balance` peut lever (arrêté absent, devise inconnue).
    # Sans lui, le `s.close()` n'est pas atteint et la connexion ne revient pas au
    # pool — invisible en SQLite local, coûteux sur Supabase où le pool fait 5.
    # Même correction que celle déjà appliquée à `synthese_epargne`.
    try:
        comptes = soldes_balance(s, date_arrete, devise)
    finally:
        s.close()
    if not comptes:
        return {}
    balance = [(str(c.numero_compte).strip(), (c.solde_net or 0.0)) for c in comptes]
    prefixes = sorted(mapping.keys(), key=lambda c: -len(c.replace(".", "")))
    realise = defaultdict(float)
    for num_bal, solde in balance:
        for compte_budget in prefixes:
            if num_bal.startswith(compte_budget.replace(".", "")):
                ligne, _sens = mapping[compte_budget]
                realise[ligne] += abs(solde)
                break
    return dict(realise)


def budget_du_mois(exercice, mois, hypothese="H1", db_path="socle/micropop.db"):
    """Budget du MOIS concerné (non linéaire)."""
    s = get_session(db_path)
    try:
        rows = s.execute(
            select(FaitBudget.ligne_budgetaire, func.sum(FaitBudget.montant_budgete))
            .where(FaitBudget.exercice == exercice, FaitBudget.hypothese == hypothese,
                   FaitBudget.mois == mois)
            .group_by(FaitBudget.ligne_budgetaire)
        ).all()
    finally:
        s.close()
    return {ligne: (m or 0.0) for ligne, m in rows}


def budget_annuel_total(exercice, hypothese="H1", db_path="socle/micropop.db"):
    """Budget ANNUEL TOTAL (somme des 12 mois) par ligne."""
    s = get_session(db_path)
    try:
        rows = s.execute(
            select(FaitBudget.ligne_budgetaire, func.sum(FaitBudget.montant_budgete))
            .where(FaitBudget.exercice == exercice, FaitBudget.hypothese == hypothese)
            .group_by(FaitBudget.ligne_budgetaire)
        ).all()
    finally:
        s.close()
    return {ligne: (m or 0.0) for ligne, m in rows}


def budget_cumule_a_date(exercice, mois, hypothese="H1", db_path="socle/micropop.db"):
    """Budget CUMULÉ À DATE (somme des mois 1..N écoulés) par ligne — budget non linéaire."""
    s = get_session(db_path)
    try:
        rows = s.execute(
            select(FaitBudget.ligne_budgetaire, func.sum(FaitBudget.montant_budgete))
            .where(FaitBudget.exercice == exercice, FaitBudget.hypothese == hypothese,
                   FaitBudget.mois <= mois)
            .group_by(FaitBudget.ligne_budgetaire)
        ).all()
    finally:
        s.close()
    return {ligne: (m or 0.0) for ligne, m in rows}


def analyse_ecart(date_arrete_courant, date_arrete_precedent, exercice, mois,
                  hypothese="H1", db_path="socle/micropop.db"):
    """Analyse d'écart, DEUX niveaux clairement distincts :
      - MENSUEL  : réalisé(N)-réalisé(N-1) vs budget DU MOIS      → % réalisation
      - CUMULÉ   : réalisé cumulé (balance)  vs budget ANNUEL TOTAL → % progression
    date_arrete_precedent = dernier arrêté du mois précédent (None si janvier)."""
    mapping = lire_mapping(db_path=db_path)
    sens = {ligne: s for _c, (ligne, s) in mapping.items()}

    real_cum = realise_cumule_par_ligne(date_arrete_courant, db_path)
    real_prev = realise_cumule_par_ligne(date_arrete_precedent, db_path)   # {} si None

    bud_mois = budget_du_mois(exercice, mois, hypothese, db_path)
    bud_annuel = budget_annuel_total(exercice, hypothese, db_path)
    bud_cum_date = budget_cumule_a_date(exercice, mois, hypothese, db_path)

    lignes = set(bud_annuel) | set(real_cum)
    out = []
    for ligne in sorted(lignes):
        rc = real_cum.get(ligne, 0.0)
        rp = real_prev.get(ligne, 0.0)
        rm = rc - rp                       # réalisé du mois
        bm = bud_mois.get(ligne, 0.0)      # budget du mois
        ba = bud_annuel.get(ligne, 0.0)    # budget annuel total
        bcd = bud_cum_date.get(ligne, 0.0) # budget cumulé à date (mois écoulés)
        out.append({
            "ligne": ligne, "sens": sens.get(ligne, "?"),
            # niveau MENSUEL
            "budget_mois": bm, "realise_mois": rm,
            "ecart_mois": rm - bm,
            "pct_realisation": (rm / bm) if bm else None,       # % réalisation du mois
            # niveau CUMULÉ — 2 lectures
            "realise_cumule": rc,
            "budget_annuel": ba,
            "ecart_annuel": rc - ba,
            "pct_progression": (rc / ba) if ba else None,       # consommation du budget annuel
            "budget_cumule_a_date": bcd,
            "ecart_a_date": rc - bcd,
            "pct_realisation_a_date": (rc / bcd) if bcd else None,  # réalisé vs prévu à date
        })
    return out



def arrete_precedent(date_arrete, db_path="socle/micropop.db", devise="USD"):
    """Arrêté de balance qui sert de BASE au réalisé mensuel, ou None.

    Le réalisé mensuel est une DIFFÉRENCE de deux cumuls : cumulé(N) − cumulé(N-1).
    Sans le cumul arrêté à la fin du mois précédent, il n'y a pas de réalisé
    mensuel — et surtout pas le cumul depuis janvier, qu'on prendrait pour tel.
    C'est l'erreur que cette fonction existe pour rendre impossible : elle dit
    explicitement « je n'ai pas de base », au lieu de laisser un cumul de sept
    mois s'afficher en face d'un budget d'un mois.

    JANVIER est le seul mois où l'absence de base est NORMALE et non un manque :
    le cumul repart de zéro au 1er janvier, donc cumulé(janvier) EST le réalisé
    de janvier. Remonter au 31/12 précédent y serait une faute — on soustrairait
    l'exercice clos tout entier.

    Renvoie le dernier arrêté strictement antérieur au 1er du mois, dans le MÊME
    exercice (jamais un arrêté de l'année précédente, pour la raison ci-dessus).
    """
    if date_arrete.month == 1:
        return None
    premier_du_mois = dt.date(date_arrete.year, date_arrete.month, 1)
    debut_exercice = dt.date(date_arrete.year, 1, 1)
    s = get_session(db_path)
    try:
        return s.execute(
            select(func.max(FaitBalance.date_arrete))
            .where(FaitBalance.date_arrete < premier_du_mois,
                   FaitBalance.date_arrete >= debut_exercice,
                   FaitBalance.devise == devise)
        ).scalar_one_or_none()
    finally:
        s.close()


def suivi_budgetaire(date_arrete, precedent=None, hypothese="H1",
                     db_path="socle/micropop.db"):
    """Suivi budgétaire complet d'un arrêté, prêt à être exposé tel quel.

    L'exercice et le mois sont DÉDUITS de l'arrêté plutôt que reçus à part :
    deux sources pour la même information finissent toujours par se contredire,
    et on comparerait alors le réalisé d'un mois au budget d'un autre sans que
    rien ne le signale.

    Le dictionnaire renvoyé porte, à côté des lignes, de quoi savoir CE QU'ON
    PEUT EN LIRE : `niveau_mensuel_disponible` est faux quand la balance du mois
    précédent manque, et les montants mensuels ne veulent alors rien dire.
    """
    d = date_arrete
    if precedent is None:
        precedent = arrete_precedent(d, db_path=db_path)

    # Janvier : pas de base à chercher, le cumul EST le mois (cf. arrete_precedent).
    # Les autres mois : sans base, le « réalisé du mois » vaudrait le cumul entier.
    janvier = d.month == 1
    mensuel_ok = janvier or precedent is not None

    lignes = analyse_ecart(d, precedent, d.year, d.month,
                           hypothese=hypothese, db_path=db_path)

    return {
        "arrete": d,
        "exercice": d.year,
        "mois": d.month,
        "hypothese": hypothese,
        "precedent": precedent,
        "niveau_mensuel_disponible": mensuel_ok,
        "motif_mensuel_absent": None if mensuel_ok else (
            f"Aucune balance de l'exercice {d.year} antérieure au mois {d.month:02d} "
            f"n'est chargée. Le réalisé mensuel est une différence de deux cumuls : "
            f"sans le cumul du mois précédent, seul le niveau CUMULÉ est exploitable."
        ),
        "lignes": lignes,
    }

if __name__ == "__main__":
    r = analyse_ecart(dt.date(2026, 7, 31), dt.date(2026, 6, 30), 2026, 7)
    print(f"{'Ligne':30s} {'B.mois':>10s} {'R.mois':>10s} {'%réal':>7s} | "
          f"{'B.annuel':>12s} {'R.cumulé':>12s} {'%prog':>7s}")
    for x in r[:12]:
        pr = f"{x['pct_realisation']:.0%}" if x['pct_realisation'] else "-"
        pp = f"{x['pct_progression']:.0%}" if x['pct_progression'] else "-"
        print(f"  {x['ligne'][:28]:28s} {x['budget_mois']:>10,.0f} {x['realise_mois']:>10,.0f} {pr:>7s} | "
              f"{x['budget_annuel']:>12,.0f} {x['realise_cumule']:>12,.0f} {pp:>7s}")
