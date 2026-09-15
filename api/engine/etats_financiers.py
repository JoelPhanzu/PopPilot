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

from sqlalchemy import select

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


def taux_change(session, date_arrete: dt.date) -> float:
    t = session.execute(
        select(ParamTauxChange.taux)
        .where(ParamTauxChange.date_effet <= date_arrete)
        .order_by(ParamTauxChange.date_effet.desc())
    ).scalars().first()
    return t or 1.0


def etats_financiers(date_arrete: dt.date, db_path="socle/micropop.db") -> dict:
    """Construit bilan (par rubrique) + compte de résultat + contrôles, USD & CDF."""
    s = get_session(db_path)
    taux = taux_change(s, date_arrete)
    comptes = s.execute(
        select(FaitBalance).where(FaitBalance.date_arrete == date_arrete)
    ).scalars().all()
    s.close()
    if not comptes:
        raise ValueError(f"Aucune balance pour l'arrêté {date_arrete}. Importer d'abord.")

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
    resultat_net = produits - charges
    # le résultat vient équilibrer le passif
    total_passif = total_passif_hors_resultat + resultat_net

    controles = {
        "bilan_equilibre_ecart": total_actif - total_passif,
        "resultat_net": resultat_net,
        "comptes_non_mappes": len(non_mappes),
        "fonds_propres": passif.get("Fonds propres", 0.0) + resultat_net,
    }

    return {
        "taux_change": taux,
        "actif": actif, "passif": passif,
        "total_actif": total_actif, "total_passif": total_passif,
        "produits": produits, "charges": charges, "resultat_net": resultat_net,
        "resultat_net_cdf": resultat_net * taux,
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
