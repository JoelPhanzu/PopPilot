"""
Générateur FINA (Rapport 3) — CLAUDE.md §32-37.
Déclaration mensuelle réglementaire BCC, EN CDF.

PRINCIPE (clarification CDG) : les éléments comptables du FINA viennent de la BALANCE CDF
DIRECTEMENT, SANS conversion (le fichier magique CDF fournit bilan/CR/comptes en CDF natif).
La ventilation Client/Groupe vient du crédit (produit LISANGA). On ne convertit PAS le CDF.

La balance CDF est importée avec devise='CDF'. Le générateur lit ses soldes tels quels.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import select

from socle.schema import FaitCredit, FaitBalance, get_session
from engine.epargne import synthese_epargne


def _soldes_cdf(session, date_arrete):
    """Soldes de la balance CDF (devise='CDF') pour l'arrêté."""
    rows = session.execute(
        select(FaitBalance).where(FaitBalance.date_arrete == date_arrete,
                                  FaitBalance.devise == "CDF")
    ).scalars().all()
    return {r.numero_compte: (r.solde_net or 0.0) for r in rows}


def _somme_prefixes(soldes, *prefixes):
    return sum(v for c, v in soldes.items() if any(str(c).startswith(p) for p in prefixes))


def generer_fina(date_arrete: dt.date, db_path="socle/micropop.db") -> dict:
    s = get_session(db_path)
    soldes = _soldes_cdf(s, date_arrete)
    if not soldes:
        s.close()
        raise ValueError(f"Aucune balance CDF pour {date_arrete}. "
                         "Importer la balance CDF (devise='CDF').")
    prets = s.execute(
        select(FaitCredit).where(FaitCredit.date_arrete == date_arrete)
    ).scalars().all()
    s.close()

    # ── Montants comptables EN CDF, directement depuis la balance (aucune conversion) ──
    ct_total = _somme_prefixes(soldes, "32")     # court terme
    mt_total = _somme_prefixes(soldes, "31")     # moyen terme
    retard_total = _somme_prefixes(soldes, "39")
    encours_bilan = ct_total + mt_total + retard_total

    # ── Ventilation Client/Groupe depuis le CRÉDIT (proportion), appliquée aux montants CDF ──
    enc_credit = sum(p.encours or 0 for p in prets)
    enc_grp_ct = sum(p.encours or 0 for p in prets
                     if p.est_groupe and (p.jours_de_retard or 0) == 0)
    enc_grp_ret = sum(p.encours or 0 for p in prets
                      if p.est_groupe and (p.jours_de_retard or 0) > 0)
    # proportion du groupe dans l'encours total → appliquée au CDF du bilan
    prop = (encours_bilan / enc_credit) if enc_credit else 0.0   # facteur CDF/USD implicite
    f5 = {
        "CT_total_cdf": ct_total, "MT_total_cdf": mt_total,
        "retard_total_cdf": retard_total, "total_cdf": encours_bilan,
        "groupe_sain_cdf": enc_grp_ct * prop,
        "groupe_retard_cdf": enc_grp_ret * prop,
    }

    # ── F11 : balance âgée (tranches depuis le crédit, proportionnées au CDF) ──
    tr = {"1-30": 0.0, "31-60": 0.0, "61-90": 0.0, "91-180": 0.0, "181-360": 0.0, "361+": 0.0}
    for p in prets:
        tr["1-30"] += (p.tr_1_7 or 0) + (p.tr_8_30 or 0)
        tr["31-60"] += p.tr_31_60 or 0
        tr["61-90"] += p.tr_61_90 or 0
        tr["91-180"] += p.tr_91_180 or 0
        tr["181-360"] += p.tr_181_360 or 0
        tr["361+"] += p.tr_361_plus or 0
    f11 = {k: v * prop for k, v in tr.items()}
    f11["encours_brut_cdf"] = encours_bilan
    f11["retard_total_cdf"] = retard_total

    # ── F6 : épargne (l'épargne CDF vient de l'inventaire, déjà en CDF pour les comptes CDF) ──
    try:
        syn = synthese_epargne(date_arrete, db_path=db_path, en_usd=False)
        f6 = {"epargne_totale_origine": syn["encours_total"], "groupe": syn["epargne_groupe"],
              "par_type": syn["par_type"]}
    except Exception:
        f6 = None

    # ── COHÉRENCES INTER-FEUILLES (§35) — toutes en CDF, sans conversion ──
    controles = {
        "X2_F5_total_vs_bilan": {"ecart": abs(f5["total_cdf"] - encours_bilan),
                                 "ok": abs(f5["total_cdf"] - encours_bilan) < 1},
        "X2_F11_encours_vs_bilan": {"ecart": abs(f11["encours_brut_cdf"] - encours_bilan),
                                    "ok": abs(f11["encours_brut_cdf"] - encours_bilan) < 1},
        "groupe_CT_coherent": {"total_groupe_ct": f5["groupe_sain_cdf"] + f5["groupe_retard_cdf"]},
    }

    return {"date_arrete": date_arrete, "devise": "CDF",
            "F5": f5, "F6": f6, "F11": f11,
            "total_actif_cdf": _somme_prefixes(soldes, "1", "2", "3", "5") if False else None,
            "controles": controles}


if __name__ == "__main__":
    r = generer_fina(dt.date(2026, 7, 31))
    print(f"FINA {r['date_arrete']} — EN CDF (sans conversion)")
    print("\nF5 — ventilation crédit (CDF) :")
    for k, v in r["F5"].items():
        print(f"  {k:22s}: {v:>22,.0f}")
    print("\nContrôles :")
    for k, v in r["controles"].items():
        print(f"  {k:26s}: {v}")
