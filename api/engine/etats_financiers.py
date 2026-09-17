"""
Moteur d'états financiers (Phase 2, Lots 2.1-2.3) — CLAUDE.md §38-42.
Portage du « fichier magique » : balance → bilan + compte de résultat normalisés BCC.

- Mapping par PRÉFIXE de compte (2 chiffres) → {destination, rubrique, type IMF} (§40).
- Comptes mixtes ACTIF/PASSIF (37,40,42-47,53,56) : le signe du solde net décide du côté.
- Conversion USD → CDF par taux de clôture daté (§42).
- Contrôles de cohérence C-1..C-5 (§41).
"""
from __future__ import annotations

import datetime as dt
import warnings as _warnings

from sqlalchemy import or_, select

from socle.schema import FaitBalance, ParamMappingCompte, ParamTauxChange, get_session

# Mapping de référence (préfixe → destination, rubrique, type IMF) — issu du fichier magique §40.
MAPPING = {
    "10": ("PASSIF", "Fonds propres", "Fonds propres"),
    "11": ("PASSIF", "Fonds propres", "Fonds propres"),
    "12": ("PASSIF", "Fonds propres", "Fonds propres"),
    "13": ("PASSIF", "Fonds propres", "Fonds propres"),
    "14": ("PASSIF", "Fonds propres", "Fonds propres"),
    "15": ("PASSIF", "Opérations diverses", "Autres"),
    "16": ("PASSIF", "Opérations diverses", "Autres"),
    "17": ("PASSIF", "Opérations diverses", "Autres"),
    "18": ("PASSIF", "Opérations diverses", "Provisions"),
    "20": ("ACTIF", "Immobilisations", "Immobilisations"),
    "22": ("ACTIF", "Immobilisations", "Immobilisations"),
    "23": ("ACTIF", "Immobilisations", "Immobilisations"),
    "24": ("ACTIF", "Immobilisations", "Immobilisations"),
    "25": ("ACTIF", "Immobilisations", "Immobilisations"),
    "26": ("ACTIF", "Immobilisations", "Immobilisations"),
    "27": ("ACTIF", "Immobilisations", "Immobilisations"),
    "28": ("ACTIF", "Immobilisations", "Immobilisations"),
    "30": ("ACTIF", "Opérations clientèle", "Portefeuille de crédit"),
    "31": ("ACTIF", "Opérations clientèle", "Portefeuille de crédit"),
    "32": ("ACTIF", "Opérations clientèle", "Portefeuille de crédit"),
    "33": ("PASSIF", "Opérations clientèle", "Épargne"),
    "34": ("PASSIF", "Opérations clientèle", "Épargne"),
    "35": ("PASSIF", "Opérations clientèle", "Épargne"),
    "36": ("PASSIF", "Opérations clientèle", "Épargne"),
    "37": ("ACTIF/PASSIF", "Opérations clientèle", "Portefeuille de crédit"),
    "38": ("ACTIF", "Opérations clientèle", "Provisions"),
    "39": ("ACTIF", "Opérations clientèle", "Portefeuille de crédit"),
    "40": ("ACTIF/PASSIF", "Opérations diverses", "Autres"),
    "42": ("ACTIF/PASSIF", "Opérations diverses", "Autres"),
    "43": ("ACTIF/PASSIF", "Opérations diverses", "Autres"),
    "44": ("ACTIF/PASSIF", "Opérations diverses", "Autres"),
    "45": ("ACTIF/PASSIF", "Opérations diverses", "Autres"),
    "46": ("ACTIF/PASSIF", "Opérations diverses", "Autres"),
    "47": ("ACTIF/PASSIF", "Opérations diverses", "Autres"),
    "48": ("ACTIF", "Opérations diverses", "Provisions"),
    "52": ("ACTIF", "Trésorerie", "Trésorerie"),
    "53": ("ACTIF/PASSIF", "Trésorerie", "Trésorerie"),
    "56": ("ACTIF/PASSIF", "Trésorerie", "Trésorerie"),
    "57": ("ACTIF", "Trésorerie", "Trésorerie"),
    "58": ("ACTIF", "Trésorerie", "Provisions"),
    "60": ("RESULTAT", "Charges financières", "Charges financières"),
    "61": ("RESULTAT", "Charges financières", "Charges financières"),
    "62": ("RESULTAT", "Charges financières", "Charges financières"),
    "63": ("RESULTAT", "Charges financières", "Charges financières"),
    "64": ("RESULTAT", "Charges d'exploitation", "Charges d'exploitation"),
    "65": ("RESULTAT", "Charges d'exploitation", "Charges d'exploitation"),
    "66": ("RESULTAT", "Charges d'exploitation", "Charges d'exploitation"),
    "67": ("RESULTAT", "Autres", "Autres"),
    "68": ("RESULTAT", "Provisions", "Provisions"),
    "69": ("RESULTAT", "Provisions", "Provisions"),
    "70": ("RESULTAT", "Produits financiers", "Produits financiers"),
    "71": ("RESULTAT", "Produits financiers", "Produits financiers"),
    "72": ("RESULTAT", "Produits financiers", "Produits financiers"),
    "73": ("RESULTAT", "Produits financiers", "Produits financiers"),
    "74": ("RESULTAT", "Autres produits", "Autres"),
    "76": ("RESULTAT", "Autres produits", "Autres"),
    "77": ("RESULTAT", "Autres produits", "Autres"),
    "78": ("RESULTAT", "Autres produits", "Autres"),
    "79": ("RESULTAT", "Autres produits", "Autres"),
    "86": ("RESULTAT", "Impôt", "Autres"),
}


def prefixe(compte: str) -> str:
    return str(compte).strip()[:2]


def filtre_devise(devise: str):
    """Condition SQL « balance de CETTE devise ».

    La devise fait partie de la clé de fait_balance : un arrêté porte la balance USD
    (bilan, indicateurs, budget) ET la balance CDF (FINA). Toute lecture doit donc
    choisir la sienne, sinon les deux s'additionnent et le total n'a plus de sens.
    Les lignes anciennes sans devise sont traitées comme des USD (la balance USD est
    la seule qui existait avant l'ajout de la devise à la clé).
    """
    if devise == "USD":
        return or_(FaitBalance.devise == "USD", FaitBalance.devise.is_(None))
    return FaitBalance.devise == devise


def soldes_balance(session, date_arrete: dt.date, devise: str = "USD") -> list:
    """Lignes de balance de l'arrêté, dans la devise demandée (jamais un mélange)."""
    return session.execute(
        select(FaitBalance).where(FaitBalance.date_arrete == date_arrete,
                                  filtre_devise(devise))
    ).scalars().all()


def taux_change(session, date_arrete: dt.date) -> float:
    """Taux USD->CDF en vigueur a l'arrete (le plus recent a date d'effet <= arrete).

    DEUX GARDE-FOUS, parce que les deux echecs etaient SILENCIEUX :

    1. Taux absent -> on LEVE. L'ancien `return t or 1.0` convertissait les USD en
       CDF au taux 1:1 : un bilan faux d'un facteur ~2268, publiable sans qu'aucune
       alerte ne se declenche. La doctrine (§42) est que le taux est saisi et jamais
       figé ; un defaut de 1.0 est precisement un taux figé, et le pire qui soit.

    2. Taux perime -> on AVERTIT. Le taux de cloture BCC change chaque mois. Rien
       n'empechait un arrete de decembre d'utiliser le taux d'aout : le calcul passe,
       les montants sont faux de quelques dixiemes de pour cent, et l'ecart ne se voit
       qu'au rapprochement. On ne bloque pas (un taux peut legitimement valoir pour
       plusieurs mois), mais ca ne passe plus inapercu.
    """
    ligne = session.execute(
        select(ParamTauxChange.date_effet, ParamTauxChange.taux)
        .where(ParamTauxChange.date_effet <= date_arrete)
        .order_by(ParamTauxChange.date_effet.desc())
    ).first()
    if ligne is None:
        raise ValueError(
            f"Aucun taux de change USD->CDF en vigueur au {date_arrete}. "
            f"Le saisir avant tout calcul en CDF : "
            f"ingest.taux_change.saisir_taux(date_effet, taux).")
    date_effet, taux = ligne
    if (date_effet.year, date_effet.month) != (date_arrete.year, date_arrete.month):
        _warnings.warn(
            f"Taux de change perime : arrete {date_arrete} calcule avec le taux du "
            f"{date_effet} ({taux}). Saisir le taux du mois pour un montant CDF exact.",
            stacklevel=2)
    return taux


def etats_financiers(date_arrete: dt.date, db_path="socle/micropop.db",
                     devise="USD") -> dict:
    """Construit bilan (par rubrique) + compte de résultat + contrôles, USD & CDF.

    `devise` = devise de la balance lue (USD par défaut : les montants USD sont la
    source de vérité, §43). La balance CDF du même arrêté, réservée au FINA, n'est
    jamais mélangée à celle-ci.
    """
    s = get_session(db_path)
    # Le taux ne sert qu'aux montants CDF dérivés. Son absence ne doit PAS empêcher un
    # bilan en USD : elle bloquait en réalité les moyennes de période (le 31/12
    # précédent n'a pas toujours de taux saisi), et les ratios ROE/ROA/B1/C3 retombaient
    # alors sur les soldes du seul arrêté — silencieusement. On dégrade la seule chose
    # qui dépend du taux (les montants CDF), et on le dit.
    try:
        taux = taux_change(s, date_arrete)
        taux_absent = None
    except ValueError as e:
        taux, taux_absent = None, str(e)
    comptes = soldes_balance(s, date_arrete, devise)
    s.close()
    if not comptes:
        raise ValueError(f"Aucune balance {devise} pour l'arrêté {date_arrete}. Importer d'abord.")

    # Le solde net (col Solde Net USD) : négatif = solde créditeur, positif = débiteur (convention
    # du fichier magique). Actif = débiteurs, Passif/Résultat produits = créditeurs.
    actif = {}         # rubrique → montant
    passif = {}
    produits = 0.0
    charges = 0.0
    par_prefixe = {}
    non_mappes = []

    for c in comptes:
        pfx = prefixe(c.numero_compte)
        solde = c.solde_net or 0.0          # signe : + débiteur, − créditeur
        par_prefixe[pfx] = par_prefixe.get(pfx, 0.0) + solde
        m = MAPPING.get(pfx)
        if m is None:
            non_mappes.append(c.numero_compte)
            continue
        dest, rubrique, _type = m
        if dest == "ACTIF":
            actif[rubrique] = actif.get(rubrique, 0.0) + solde
        elif dest == "PASSIF":
            passif[rubrique] = passif.get(rubrique, 0.0) - solde   # crédit → positif au passif
        elif dest == "ACTIF/PASSIF":
            if solde >= 0:
                actif[rubrique] = actif.get(rubrique, 0.0) + solde
            else:
                passif[rubrique] = passif.get(rubrique, 0.0) - solde
        elif dest == "RESULTAT":
            # produits (7x) créditeurs (solde négatif), charges (6x) débiteurs (positif)
            if pfx.startswith("7") or pfx in ("78", "79"):
                produits += -solde
            else:
                charges += solde

    total_actif = sum(actif.values())
    total_passif_hors_resultat = sum(passif.values())
    # ATTENTION AU NOM : produits - charges est le resultat COMPTABLE, avant impot.
    # La doctrine (§67) veut : resultat net = comptable - IBP, avec
    # IBP = (comptable + reintegrations) x taux, calcule A L'ARRETE ANNUEL.
    # Ce moteur ne deduit AUCUN impot : en cours d'annee c'est correct (le compte 13
    # vaut 0, resultat FINA F1 valide contre le gabarit), mais au 31/12 la valeur
    # ci-dessous reste un resultat AVANT impot. On l'expose sous les deux noms pour
    # que personne ne prenne l'un pour l'autre, et on signale le cas au 31/12.
    resultat_comptable = produits - charges
    resultat_net = resultat_comptable
    # le résultat vient équilibrer le passif
    total_passif = total_passif_hors_resultat + resultat_net

    # Au 31/12, un resultat presente comme "net" sans IBP est faux (et surevalue le
    # ROE/ROA qui le consomment). Tant que le moteur IBP n'existe pas, on le dit.
    ibp_du = (date_arrete.month, date_arrete.day) == (12, 31)
    if ibp_du:
        _warnings.warn(
            f"Arrete annuel {date_arrete} : 'resultat_net' est le resultat COMPTABLE "
            f"avant impot. L'IBP (§67) n'est pas deduit — grille de reintegrations "
            f"DAF non fournie. Les ratios ROE/ROA en decoulant sont surevalues.",
            stacklevel=2)

    controles = {
        "bilan_equilibre_ecart": total_actif - total_passif,
        "resultat_net": resultat_net,
        "resultat_comptable": resultat_comptable,
        "ibp_deduit": False,
        "ibp_du_a_cet_arrete": ibp_du,
        "comptes_non_mappes": len(non_mappes),
        "fonds_propres": passif.get("Fonds propres", 0.0) + resultat_net,
        "taux_absent": taux_absent,          # None si le taux du mois est bien saisi
    }

    return {
        "taux_change": taux,
        "actif": actif, "passif": passif,
        "total_actif": total_actif, "total_passif": total_passif,
        "produits": produits, "charges": charges, "resultat_net": resultat_net,
        "resultat_comptable": resultat_comptable,
        # pas de taux saisi → pas de montant CDF du tout (jamais un taux figé, §42)
        "resultat_net_cdf": (resultat_net * taux) if taux else None,
        "controles": controles,
        "comptes_non_mappes": non_mappes,
        "par_prefixe": par_prefixe,
    }


if __name__ == "__main__":
    import sys
    arr = dt.date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else dt.date(2026, 7, 31)
    r = etats_financiers(arr)
    print(f"Total actif   : {r['total_actif']:,.2f} USD")
    print(f"Total passif  : {r['total_passif']:,.2f} USD")
    print(f"Produits      : {r['produits']:,.2f}")
    print(f"Charges       : {r['charges']:,.2f}")
    print(f"Résultat net  : {r['resultat_net']:,.2f} USD")
    print(f"Contrôles     : {r['controles']}")
