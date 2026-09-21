"""
États financiers DÉTAILLÉS — le référentiel BCC ligne à ligne, comptes compris.

Complète `engine/etats_financiers.py` sans le modifier : celui-ci rend quatre
rubriques par côté (agrégat validé à écart nul, qui reste la référence), celui-là
rend les 32 lignes de l'actif, les 28 du passif et les 26 du compte de résultat,
chacune avec les comptes de balance qui la composent.

INVARIANT — le total général de ce module est le MÊME que celui de l'agrégat.
Deux chemins de calcul aboutissant au même nombre, c'est un contrôle gratuit :
`controles.ecart_avec_agregat` le publie à chaque appel, et il doit rester nul.
S'il ne l'est pas, c'est qu'un compte de la balance n'entre pas dans le
référentiel — la liste `comptes_non_places` dit alors lesquels.
"""
from __future__ import annotations

import datetime as dt

from engine.etats_financiers import etats_financiers, prefixe, soldes_balance
from engine.referentiel_etats import (
    ACTIF, CODE_RESULTAT_PASSIF, Ligne, PASSIF, RESULTAT, SousTotal,
    prefixes_connus,
)
from socle.schema import get_session

#  Seuil d'équilibre du bilan. Le fichier magique lui-même affiche −0,0065 au
#  31/05/2026 (cumul d'arrondis sur ~2 000 comptes) : un seuil plus serré
#  déclarerait « déséquilibré » un bilan que la comptabilité tient pour juste.
#  Assez serré, en revanche, pour ne rien absorber de réel — la balance d'avril
#  2026 sort à −19 959,48, et elle DOIT sortir en anomalie.
TOLERANCE = 0.01


def _regrouper(comptes) -> tuple[dict[str, float], dict[str, list[dict]]]:
    """Balance → somme par préfixe, et liste des comptes par préfixe."""
    sommes: dict[str, float] = {}
    detail: dict[str, list[dict]] = {}
    for c in comptes:
        pfx = prefixe(c.numero_compte)
        solde = c.solde_net or 0.0
        sommes[pfx] = sommes.get(pfx, 0.0) + solde
        detail.setdefault(pfx, []).append({
            "numero_compte": str(c.numero_compte).strip(),
            "libelle": c.libelle,
            "solde_net": solde,
        })
    return sommes, detail


def _comptes_de(ligne: Ligne, detail: dict[str, list[dict]]) -> list[dict]:
    """Comptes de balance qui alimentent cette ligne.

    Pour un préfixe partagé actif/passif (37, 40 à 47, 53, 56), le tri se fait
    COMPTE PAR COMPTE, et non sur le solde cumulé du préfixe : c'est le signe de
    CHAQUE compte qui décide de son côté. Le référentiel le montre sans
    ambiguïté — au 31/05/2026, le préfixe (46) alimente simultanément
    « Débiteurs divers » à l'actif (33 467,11) et « Créditeurs divers » au passif
    (55 869,42). Trier sur le cumul du préfixe aurait mis les deux du même côté
    et faussé le total général de 120 290,81.

    Même règle que le moteur agrégé (`dest == "ACTIF/PASSIF"`, arbitrage sur
    `solde >= 0` compte par compte), afin que les deux chemins de calcul ne
    puissent pas diverger.
    """
    comptes: list[dict] = []
    for p in ligne.prefixes:
        comptes.extend(detail.get(p, []))
    if not ligne.mixte:
        return comptes
    if ligne.orientation > 0:          # ligne d'actif : les comptes débiteurs
        return [c for c in comptes if c["solde_net"] >= 0]
    return [c for c in comptes if c["solde_net"] < 0]   # passif : les créditeurs


def _construire(etat, sommes, detail, injections=None) -> list[dict]:
    """Peuple un état du référentiel. `injections` force le montant d'un code."""
    injections = injections or {}
    montants: dict[str, float] = {}
    sortie: list[dict] = []

    #  Les lignes d'abord : un sous-total ne peut se calculer qu'après elles.
    #  On garde l'ORDRE du référentiel pour la sortie, d'où les deux passes.
    comptes_par_code: dict[str, list[dict]] = {}
    for item in etat:
        if isinstance(item, Ligne):
            comptes = _comptes_de(item, detail)
            comptes_par_code[item.code] = comptes
            montants[item.code] = item.orientation * sum(c["solde_net"] for c in comptes)

    for code, valeur in injections.items():
        montants[code] = valeur

    #  Les sous-totaux, du plus profond au plus haut : on itère jusqu'à ce que
    #  tout soit résolu, sans supposer un ordre de déclaration particulier.
    a_resoudre = [i for i in etat if isinstance(i, SousTotal)]
    signes = {i.code: getattr(i, "signe", 1) for i in etat}
    for _ in range(len(a_resoudre) + 1):
        reste = []
        for st in a_resoudre:
            if all(c in montants for c in st.composants):
                montants[st.code] = sum(
                    signes.get(c, 1) * montants[c] for c in st.composants)
            else:
                reste.append(st)
        a_resoudre = reste
        if not a_resoudre:
            break
    if a_resoudre:
        manquants = ", ".join(st.code for st in a_resoudre)
        raise ValueError(f"Référentiel incohérent : sous-totaux non résolus ({manquants}).")

    for item in etat:
        if isinstance(item, SousTotal):
            sortie.append({
                "code": item.code,
                "libelle": item.libelle,
                "nature": "total_general" if item.total_general else "sous_total",
                "montant": montants[item.code],
                "signe": 1,
                "comptes": [],
            })
        else:
            #  Une ligne sans compte de son côté reste PUBLIÉE, à zéro : le
            #  référentiel BCC l'attend, et une ligne absente est une anomalie
            #  de déclaration.
            comptes = comptes_par_code[item.code]
            sortie.append({
                "code": item.code,
                "libelle": item.libelle,
                "nature": "ligne",
                "montant": montants[item.code],
                "signe": item.signe,
                "prefixes": list(item.prefixes),
                "comptes": sorted(comptes, key=lambda c: c["numero_compte"]),
            })
    return sortie


def etats_detailles(date_arrete: dt.date, db_path="socle/micropop.db",
                    devise="USD") -> dict:
    """Bilan et compte de résultat, au format exact du référentiel BCC."""
    s = get_session(db_path)
    try:
        comptes = soldes_balance(s, date_arrete, devise)
    finally:
        s.close()
    if not comptes:
        raise ValueError(f"Aucune balance {devise} pour l'arrêté {date_arrete}. Importer d'abord.")

    sommes, detail = _regrouper(comptes)

    #  L'agrégat validé sert de témoin : mêmes données, autre chemin.
    agregat = etats_financiers(date_arrete, db_path=db_path, devise=devise)

    resultat = _construire(RESULTAT, sommes, detail)
    resultat_net = next(l["montant"] for l in resultat if l["code"] == "V1.F1.26")

    #  (13) Résultat net au passif : le compte 13 vaut 0 tant que le résultat
    #  n'est pas affecté (en cours d'année). Le référentiel y attend pourtant le
    #  résultat de l'exercice — sinon le passif ne boucle pas. On prend donc le
    #  compte 13 s'il porte quelque chose, le résultat CALCULÉ sinon, et on dit
    #  lequel : additionner les deux compterait le résultat en double.
    solde_13 = -sommes.get("13", 0.0)
    depuis_compte_13 = abs(solde_13) > TOLERANCE
    injection = {CODE_RESULTAT_PASSIF: solde_13 if depuis_compte_13 else resultat_net}

    actif = _construire(ACTIF, sommes, detail)
    passif = _construire(PASSIF, sommes, detail, injections=injection)

    total_actif = next(l["montant"] for l in actif if l["code"] == "V1.F0a.01")
    total_passif = next(l["montant"] for l in passif if l["code"] == "V1.F0p.01")

    connus = prefixes_connus()
    non_places = sorted({
        c["numero_compte"]
        for pfx, lignes in detail.items() if pfx not in connus
        for c in lignes
    })

    return {
        "date_arrete": date_arrete,
        "devise": devise,
        "actif": actif,
        "passif": passif,
        "resultat": resultat,
        "total_actif": total_actif,
        "total_passif": total_passif,
        "resultat_net": resultat_net,
        "resultat_source": "compte 13 (résultat affecté)" if depuis_compte_13
                           else "calculé sur les classes 6 et 7 (compte 13 à zéro)",
        "controles": {
            "bilan_equilibre_ecart": total_actif - total_passif,
            "equilibre": abs(total_actif - total_passif) <= TOLERANCE,
            #  Les deux chemins doivent donner le même total. Un écart signale
            #  un compte que le référentiel ne sait pas placer.
            "ecart_avec_agregat": total_actif - agregat["total_actif"],
            "ecart_resultat_avec_agregat": resultat_net - agregat["resultat_net"],
            "comptes_non_places": non_places,
            "nb_comptes_non_places": len(non_places),
            "nb_comptes_balance": len(comptes),
        },
    }


if __name__ == "__main__":
    import sys
    arr = dt.date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else dt.date(2026, 5, 31)
    r = etats_detailles(arr)
    for etat, titre in ((r["actif"], "ACTIF"), (r["passif"], "PASSIF"), (r["resultat"], "RESULTAT")):
        print(f"\n===== {titre} =====")
        for l in etat:
            marque = "  " if l["nature"] == "ligne" else "* "
            print(f"{marque}{l['code']:12s} {l['libelle'][:62]:62s} {l['montant']:>16,.2f}")
    c = r["controles"]
    print(f"\nEcart bilan            : {c['bilan_equilibre_ecart']:,.6f}")
    print(f"Ecart avec l'agregat   : {c['ecart_avec_agregat']:,.6f}")
    print(f"Ecart resultat/agregat : {c['ecart_resultat_avec_agregat']:,.6f}")
    print(f"Comptes non places     : {c['nb_comptes_non_places']}")
