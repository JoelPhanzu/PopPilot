"""
PopPilot API — tableau de bord crédit FILTRÉ (GET /credit/filtre, GET /credit/filtres/valeurs).

STRICTEMENT ADDITIF : /par et /provisions restent tels quels. Ce routeur ne réécrit aucun
calcul, il enchaîne trois briques existantes :
  1. engine.moteur_filtres.filtrer_prets — sélectionne les prêts (agence, sexe, produit,
     durée, client, agent, superviseur) AVANT tout calcul ;
  2. engine.par._agrege — le PAR/encours exact de /par, appliqué à la sélection ;
  3. engine.derivation.charger_bareme / taux_provision — le barème de /provisions.
Sans filtre, les chiffres sont donc ceux de /par et /provisions au centime
(tests/test_filtres_credit.py le vérifie sur l'extraction réelle de mai).

COMPLÉMENT MANUEL DAF (provision Goma) : c'est un montant saisi PAR AGENCE, il n'a ni sexe,
ni produit, ni agent. Il n'est ajouté que si la sélection garde des agences entières (aucun
filtre, ou filtre agence seul). Dès qu'un filtre descend sous l'agence, il est exclu et la
réponse le DIT (`complement_manuel_inclus: false`) — le répartir serait inventer une clé.

CLOISONNEMENT : un rôle AGENCE est ramené de force à son agence ; demander une autre agence
est refusé (403), pas ignoré en silence. Les menus déroulants ne listent que ses valeurs.
"""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select

from socle.schema import FaitCredit, ProvisionManuelle, get_session
from engine.moteur_filtres import filtrer_prets, valeurs_de_filtres
from engine.par import _agrege
from engine.derivation import charger_bareme, taux_provision

from auth_supabase import ROLES_ACCES_TOTAL, utilisateur_courant

routeur = APIRouter(tags=["credit-filtres"])

DUREES = {"court", "moyen", "long"}

# Seules colonnes lues par moteur_filtres, par._agrege et derivation.taux_provision.
# fait_credit en compte 36 : charger les objets ORM complets depuis Supabase prend
# ~85 s pour un arrêté. On lit ces 10 colonnes en lignes SQL simples (Row : accès
# par attribut, comme l'objet ORM) — quelques secondes. Un attribut absent de cette
# liste lèverait AttributeError — jamais une valeur fausse.
_COLONNES = (FaitCredit.agence, FaitCredit.agent_credit, FaitCredit.superviseur,
             FaitCredit.sexe, FaitCredit.produit_credit, FaitCredit.numero_client,
             FaitCredit.est_groupe, FaitCredit.duree, FaitCredit.encours,
             FaitCredit.jours_de_retard)


def _d(s: str) -> dt.date:
    try:
        return dt.date.fromisoformat(s)
    except ValueError:
        raise HTTPException(400, f"Date invalide : {s} (format attendu AAAA-MM-JJ)")


def _charger_prets(arrete: dt.date):
    s = get_session()
    try:
        prets = s.execute(select(*_COLONNES).where(FaitCredit.date_arrete == arrete)).all()
    finally:
        s.close()
    if not prets:
        raise ValueError(f"Aucun prêt pour l'arrêté {arrete}. Importer d'abord l'extraction.")
    return prets


def _agence_imposee(user: dict, agence: str | None) -> str | None:
    """Rend l'agence effective. AGENCE : toujours la sienne ; une autre demandée → 403."""
    if user["role"] in ROLES_ACCES_TOTAL:
        return agence or None
    sienne = user.get("agence")
    if not sienne:
        raise HTTPException(403, "Profil AGENCE sans agence rattachée : aucune donnée visible.")
    if agence and agence != sienne:
        raise HTTPException(403, f"Accès limité à {sienne}.")
    return sienne


def _ligne(l) -> dict:
    return {"encours": l.encours, "par1": l.par1, "par30": l.par30, "par90": l.par90,
            "pct_par1": l.pct_par1, "pct_par30": l.pct_par30, "pct_par90": l.pct_par90,
            "nb_credits": l.nb_credits, "nb_clients": l.nb_clients}


@routeur.get("/credit/filtres/valeurs")
def endpoint_valeurs_filtres(arrete: str = Query(..., description="Date d'arrêté AAAA-MM-JJ"),
                             user: dict = Depends(utilisateur_courant)):
    """Valeurs des menus déroulants, limitées au périmètre visible de l'appelant."""
    prets = _charger_prets(_d(arrete))
    agence = _agence_imposee(user, None)
    if agence:
        prets = filtrer_prets(prets, agence=agence)
    return {"arrete": arrete, **valeurs_de_filtres(prets)}


@routeur.get("/credit/filtre")
def endpoint_credit_filtre(
        arrete: str = Query(..., description="Date d'arrêté AAAA-MM-JJ"),
        agence: str | None = None,
        sexe: str | None = None,
        produits: list[str] | None = Query(None, description="Répétable : ?produits=A&produits=B"),
        duree: str | None = Query(None, description="court | moyen | long"),
        client: str | None = None,
        agent: str | None = None,
        superviseur: str | None = None,
        user: dict = Depends(utilisateur_courant)):
    """Encours, PAR1/30/90 et provisions sur la sélection de prêts demandée."""
    date_arrete = _d(arrete)
    if duree and duree not in DUREES:
        raise HTTPException(422, f"duree inconnue : {duree} (attendu : court, moyen, long)")
    if sexe and sexe.upper() not in {"F", "H"}:
        raise HTTPException(422, f"sexe inconnu : {sexe} (attendu : F ou H)")

    agence = _agence_imposee(user, agence)
    tous = _charger_prets(date_arrete)
    prets = filtrer_prets(tous, agence=agence, agent=agent, superviseur=superviseur, sexe=sexe,
                          produits=produits, client=client, duree=duree)

    filtres = {k: v for k, v in {"agence": agence, "sexe": sexe, "produits": produits,
                                 "duree": duree, "client": client, "agent": agent,
                                 "superviseur": superviseur}.items() if v}
    sous_agence = any(k != "agence" for k in filtres)

    # Provisions : barème de /provisions appliqué prêt par prêt à la sélection.
    s = get_session()
    try:
        bareme = charger_bareme(s, date_arrete)
        manuelles = s.execute(select(ProvisionManuelle).where(
            ProvisionManuelle.date_arrete == date_arrete)).scalars().all()
    finally:
        s.close()

    prov_agence: dict[str, float] = {}
    for p in prets:
        taux, _code, _tranche = taux_provision(bareme, p.jours_de_retard or 0)
        prov_agence[p.agence] = prov_agence.get(p.agence, 0.0) + (p.encours or 0.0) * taux
    prov_bareme = sum(prov_agence.values())

    # Complément DAF : seulement pour des agences ENTIÈRES présentes dans la sélection.
    agences_sel = {(p.agence or "").strip().upper(): p.agence for p in prets}
    complement = 0.0
    complements_exclus = []
    for pm in manuelles:
        cle = pm.agence.strip().upper()
        if cle not in agences_sel:
            continue                          # agence hors sélection
        if sous_agence:
            complements_exclus.append(pm.agence)
            continue
        complement += pm.montant
        lib = agences_sel[cle]
        prov_agence[lib] = prov_agence.get(lib, 0.0) + pm.montant

    # Détail par agence de la sélection (déjà cloisonnée).
    groupes: dict[str, list] = {}
    for p in prets:
        groupes.setdefault(p.agence or "(sans agence)", []).append(p)
    agences = []
    for nom, lst in sorted(groupes.items()):
        a = _agrege(lst, nom, "AGENCE")
        agences.append({"agence": nom, **_ligne(a), "provision": prov_agence.get(nom, 0.0)})

    return {
        "arrete": arrete,
        "role": user["role"],
        "portee": agence or "MICROPOP",
        "filtres": filtres,
        "nb_prets_selectionnes": len(prets),
        "global": _ligne(_agrege(prets, agence or "MICROPOP", "GLOBAL")),
        "provisions": {
            "bareme": prov_bareme,
            "complement_manuel": complement,
            "total": prov_bareme + complement,
            "complement_manuel_inclus": not sous_agence,
            "complements_exclus": complements_exclus,
        },
        "agences": agences,
    }


# ─────────────────────────────────────────────────────────────────────────────
# TABLEAU DE BORD COMPLET (colonnes du DailyTool, doctrine flux / stock)
# ─────────────────────────────────────────────────────────────────────────────
# Champs réservés aux rôles à accès total, comme /provisions et /migrations : un rôle AGENCE
# reçoit sa ligne (encours, PAR, décaissements, objectifs…) mais pas ces agrégats de risque.
_RESERVES = ("provisions", "complement_daf", "cout_du_risque", "entree_par_nb",
             "entree_par_montant", "migration_vers")


@routeur.get("/credit/tableau-de-bord")
def endpoint_tableau_de_bord(
        arrete: str = Query(..., description="Date de VALORISATION des stocks (AAAA-MM-JJ)"),
        debut: str | None = Query(None, description="Début de la période de FLUX (défaut : 1er du mois)"),
        fin: str | None = Query(None, description="Fin de la période de FLUX (défaut : arrêté)"),
        precedent: str | None = Query(None, description="Arrêté M-1 (défaut : fin du mois précédent chargée)"),
        niveau: str = Query("agence", description="agence | superviseur | agent"),
        agence: str | None = None, sexe: str | None = None,
        produits: list[str] | None = Query(None), duree: str | None = None,
        client: str | None = None, agent: str | None = None, superviseur: str | None = None,
        user: dict = Depends(utilisateur_courant)):
    """Stocks à l'arrêté, flux sur [début ; fin], comparaison M-1, par agence / superviseur / agent."""
    from engine.tableau_de_bord_credit import NIVEAUX, tableau_de_bord_credit
    if niveau not in NIVEAUX:
        raise HTTPException(422, f"niveau inconnu : {niveau} (attendu {', '.join(NIVEAUX)})")
    if duree and duree not in DUREES:
        raise HTTPException(422, f"duree inconnue : {duree} (attendu : court, moyen, long)")
    if sexe and sexe.upper() not in {"F", "H"}:
        raise HTTPException(422, f"sexe inconnu : {sexe} (attendu : F ou H)")
    agence = _agence_imposee(user, agence)
    filtres = {"agence": agence, "sexe": sexe, "produits": produits, "duree": duree,
               "client": client, "agent": agent, "superviseur": superviseur}
    r = tableau_de_bord_credit(_d(arrete), _d(debut) if debut else None, _d(fin) if fin else None,
                               _d(precedent) if precedent else None, niveau, filtres)
    r["role"] = user["role"]
    if user["role"] not in ROLES_ACCES_TOTAL:
        r["lignes"][0]["designation"] = agence            # sa ligne, jamais « MICROPOP »
        for l in r["lignes"]:
            for cle in _RESERVES:
                l[cle] = None
        r["reserves_masques"] = list(_RESERVES)
    return r
