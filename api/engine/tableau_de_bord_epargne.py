"""
Tableau de bord ÉPARGNE (même exigence que le crédit) — doctrine FLUX / STOCK.

Source unique : l'inventaire dépôt (fait_epargne), un instantané par mois.
  - STOCK à la date de valorisation (inventaire de l'arrêté) : encours (solde actuel), comptes,
    comptes créditeurs, épargnants (clients distincts), ventilation à vue / à terme / obligatoire,
    en devise d'ORIGINE (USD, CDF) et en total USD (CDF converti au taux de l'arrêté, §42).
  - STOCK M-1 (inventaire précédent) → croissance.
  - FLUX sur [début ; fin] : dépôts et retraits des inventaires dont l'arrêté tombe dans la
    période. ⚠️ L'inventaire donne les mouvements DU MOIS : la période se lit donc par mois
    entiers (un jour isolé n'est pas visible). Chaque mois est converti à SON taux.
  - Couverture = épargne / encours crédit de la même agence au même arrêté (critère des primes
    support : ≥ 60 %).

NIVEAUX : agence | produit | type (à vue / à terme / obligatoire) | client (limité aux plus gros
soldes). FILTRES : agence, devise, type_depot, sexe (H = « 1 », F = « 2 », PM = non renseigné),
groupe (oui / non). INVARIANT : Σ lignes = total, pour les montants et les comptes (les
épargnants, clients distincts, ne s'additionnent pas entre lignes).

Aucune règle nouvelle : même classification des produits et même conversion que engine.epargne
(total inchangé : sans filtre, l'encours égale synthese_epargne au centime).
"""
from __future__ import annotations

import datetime as dt
from collections import defaultdict

from sqlalchemy import case, func, select

from socle.schema import FaitCredit, FaitEpargne, get_session

NIVEAUX = ("agence", "produit", "type", "client")
SEXES = {"H": "1", "F": "2"}
_COL_NIVEAU = {"agence": FaitEpargne.agence, "produit": FaitEpargne.libelle_produit,
               "type": FaitEpargne.type_depot, "client": FaitEpargne.id_client}
LIBELLE_TYPE = {"a_vue": "À vue", "a_terme": "À terme", "obligatoire": "Obligatoire"}


def _conditions(filtres: dict) -> list:
    E = FaitEpargne
    c = []
    if filtres.get("agence"):
        c.append(E.agence == filtres["agence"])
    if filtres.get("devise"):
        c.append(E.devise == filtres["devise"].upper())
    if filtres.get("type_depot"):
        c.append(E.type_depot == filtres["type_depot"])
    if filtres.get("sexe"):
        sx = filtres["sexe"].upper()
        c.append(E.sexe.is_(None) if sx == "PM" else E.sexe == SEXES[sx])
    if filtres.get("groupe") in ("oui", "non"):
        c.append(E.est_groupe.is_(filtres["groupe"] == "oui"))
    return c


def _inventaires(s) -> list[dt.date]:
    return sorted(d for (d,) in s.execute(select(FaitEpargne.date_arrete).distinct()))


def _usd(taux: float):
    """Expression SQL : montant converti en USD (CDF ÷ taux)."""
    return lambda col: case((FaitEpargne.devise == "CDF", col / taux), else_=col)


def _stock(s, date_arrete, taux, conditions, col):
    """{clé: {...}} agrégé en SQL sur l'inventaire d'un arrêté."""
    E, usd = FaitEpargne, _usd(taux)
    lignes = s.execute(select(
        col, E.devise, E.type_depot, func.count(),
        func.sum(case((E.solde_actuel > 0, 1), else_=0)),
        func.sum(E.solde_actuel), func.sum(usd(E.solde_actuel)),
    ).where(E.date_arrete == date_arrete, *conditions).group_by(col, E.devise, E.type_depot)).all()
    r = defaultdict(lambda: {"encours": 0.0, "encours_usd_origine": 0.0, "encours_cdf_origine": 0.0,
                             "nb_comptes": 0, "nb_comptes_crediteurs": 0,
                             "a_vue": 0.0, "a_terme": 0.0, "obligatoire": 0.0})
    for cle, devise, type_depot, n, crediteurs, solde, solde_usd in lignes:
        x = r[cle]
        x["encours"] += solde_usd or 0.0
        x["encours_usd_origine" if devise != "CDF" else "encours_cdf_origine"] += solde or 0.0
        x["nb_comptes"] += n
        x["nb_comptes_crediteurs"] += crediteurs or 0
        if type_depot in ("a_vue", "a_terme", "obligatoire"):
            x[type_depot] += solde_usd or 0.0
    return r


def _epargnants(s, date_arrete, conditions, col) -> tuple[dict, int]:
    E = FaitEpargne
    par = dict(s.execute(select(col, func.count(func.distinct(E.id_client))).where(
        E.date_arrete == date_arrete, *conditions).group_by(col)).all())
    total = s.execute(select(func.count(func.distinct(E.id_client))).where(
        E.date_arrete == date_arrete, *conditions)).scalar_one()
    return par, total


def tableau_de_bord_epargne(date_arrete: dt.date, debut: dt.date | None = None,
                            fin: dt.date | None = None, niveau: str = "agence",
                            filtres: dict | None = None, db_path="socle/micropop.db",
                            limite: int = 300) -> dict:
    if niveau not in NIVEAUX:
        raise ValueError(f"niveau inconnu : {niveau} (attendu {', '.join(NIVEAUX)})")
    fin = fin or date_arrete
    debut = debut or fin.replace(day=1)
    if debut > fin:
        raise ValueError(f"période de flux inversée : {debut} > {fin}")
    filtres = {k: v for k, v in (filtres or {}).items() if v}
    if filtres.get("sexe") and filtres["sexe"].upper() not in ("H", "F", "PM"):
        raise ValueError(f"sexe inconnu : {filtres['sexe']} (attendu H, F ou PM)")
    from engine.etats_financiers import taux_change

    E = FaitEpargne
    col = _COL_NIVEAU[niveau]
    cond = _conditions(filtres)
    s = get_session(db_path)
    try:
        inventaires = _inventaires(s)
        if date_arrete not in inventaires:
            dispo = ", ".join(d.isoformat() for d in inventaires) or "aucun"
            raise ValueError(f"Aucun inventaire épargne pour l'arrêté {date_arrete}. "
                             f"Inventaires chargés : {dispo}.")
        taux = taux_change(s, date_arrete)
        stock = _stock(s, date_arrete, taux, cond, col)
        total = _stock(s, date_arrete, taux, cond, E.date_arrete)[date_arrete]
        ep_par, ep_total = _epargnants(s, date_arrete, cond, col)

        precedents = [d for d in inventaires if d < date_arrete.replace(day=1)]
        precedent = precedents[-1] if precedents else None
        stock_m1, total_m1 = {}, None
        if precedent:
            t1 = taux_change(s, precedent)
            stock_m1 = _stock(s, precedent, t1, cond, col)
            total_m1 = _stock(s, precedent, t1, cond, E.date_arrete).get(precedent)

        # FLUX : inventaires dont l'arrêté est dans [début ; fin], chacun à son taux.
        mois_flux = [d for d in inventaires if debut <= d <= fin]
        flux = defaultdict(lambda: {"depots": 0.0, "retraits": 0.0, "nb_depots": 0, "nb_retraits": 0})
        flux_total = {"depots": 0.0, "retraits": 0.0, "nb_depots": 0, "nb_retraits": 0}
        par_mois = []
        for d in mois_flux:
            usd = _usd(taux_change(s, d))
            lignes = s.execute(select(
                col, func.sum(usd(E.montant_depot)), func.sum(usd(E.montant_retrait)),
                func.sum(case((E.montant_depot > 0, 1), else_=0)),
                func.sum(case((E.montant_retrait > 0, 1), else_=0)),
            ).where(E.date_arrete == d, *cond).group_by(col)).all()
            m = {"mois": d.isoformat(), "depots": 0.0, "retraits": 0.0}
            for cle, dep, ret, nd, nr in lignes:
                f = flux[cle]
                for k, v in (("depots", dep), ("retraits", ret), ("nb_depots", nd), ("nb_retraits", nr)):
                    f[k] += v or 0
                    flux_total[k] += v or 0
                m["depots"] += dep or 0.0
                m["retraits"] += ret or 0.0
            par_mois.append(m)

        # Couverture épargne / encours crédit (même agence, même arrêté).
        credit = {}
        if niveau == "agence":
            credit = dict(s.execute(select(FaitCredit.agence, func.sum(FaitCredit.encours)).where(
                FaitCredit.date_arrete == date_arrete).group_by(FaitCredit.agence)).all())
        credit_total = s.execute(select(func.sum(FaitCredit.encours)).where(
            FaitCredit.date_arrete == date_arrete,
            *([FaitCredit.agence == filtres["agence"]] if filtres.get("agence") else []))).scalar()
    finally:
        s.close()

    def ligne(designation, cle, x, x_m1, f, epargnants, encours_credit):
        return {
            "designation": designation, "cle": cle,
            **{k: x.get(k, 0) for k in ("encours", "encours_usd_origine", "encours_cdf_origine",
                                         "nb_comptes", "nb_comptes_crediteurs", "a_vue", "a_terme",
                                         "obligatoire")},
            "nb_epargnants": epargnants,
            "encours_m1": x_m1["encours"] if x_m1 else None,
            "croissance": (x["encours"] / x_m1["encours"] - 1) if x_m1 and x_m1["encours"] else None,
            "depots": f["depots"], "retraits": f["retraits"],
            "collecte_nette": f["depots"] - f["retraits"],
            "nb_depots": f["nb_depots"], "nb_retraits": f["nb_retraits"],
            "encours_credit": encours_credit,
            "couverture_credit": (x["encours"] / encours_credit) if encours_credit else None,
        }

    vide = {"depots": 0.0, "retraits": 0.0, "nb_depots": 0, "nb_retraits": 0}
    # La couverture n'a de sens que sur toute l'épargne d'une agence (ou de MICROPOP) :
    # un filtre devise / type / sexe / groupe découpe l'épargne, pas le crédit.
    sans_filtre_agence = not any(k != "agence" for k in filtres)
    lignes = [ligne(filtres.get("agence") or "MICROPOP", None, total, total_m1, flux_total, ep_total,
                    credit_total if sans_filtre_agence else None)]

    cles = sorted(set(stock) | set(flux), key=lambda k: -(stock[k]["encours"] if k in stock else 0.0))
    nb_lignes_total = len(cles)
    if niveau == "client":
        cles = cles[:limite]
    else:
        cles = sorted(cles, key=lambda k: str(k or ""))
    for k in cles:
        nom = (LIBELLE_TYPE.get(k, k) if niveau == "type" else k) or "(non renseigné)"
        lignes.append(ligne(nom, k, stock.get(k, {"encours": 0.0}), stock_m1.get(k), flux.get(k, vide),
                            ep_par.get(k, 0),
                            credit.get(k) if niveau == "agence" and sans_filtre_agence else None))

    return {"arrete": date_arrete.isoformat(), "debut": debut.isoformat(), "fin": fin.isoformat(),
            "precedent": precedent.isoformat() if precedent else None, "niveau": niveau,
            "filtres": filtres, "taux_change": taux,
            "inventaires_disponibles": [d.isoformat() for d in reversed(inventaires)],
            "mois_de_flux": [d.isoformat() for d in mois_flux], "flux_par_mois": par_mois,
            "nb_lignes_total": nb_lignes_total, "lignes": lignes,
            "message": None if mois_flux else (
                f"Aucun inventaire dans la période {debut} → {fin} : dépôts et retraits à 0. "
                "Les flux d'épargne se lisent par mois entiers (inventaire mensuel).")}


def top_epargnants(date_arrete: dt.date, n: int = 10, filtres: dict | None = None,
                   db_path="socle/micropop.db") -> list[dict]:
    """Top N épargnants (solde total converti en USD, tous comptes du client cumulés)."""
    from engine.etats_financiers import taux_change
    E = FaitEpargne
    s = get_session(db_path)
    try:
        usd = _usd(taux_change(s, date_arrete))
        solde = func.sum(usd(E.solde_actuel))
        lignes = s.execute(select(
            E.id_client, func.min(E.agence), func.count(), solde,
        ).where(E.date_arrete == date_arrete, *_conditions(filtres or {}))
            .group_by(E.id_client).order_by(solde.desc()).limit(n)).all()
    finally:
        s.close()
    return [{"id_client": c, "agence": a, "nb_comptes": k, "solde_usd": v or 0.0}
            for c, a, k, v in lignes]
