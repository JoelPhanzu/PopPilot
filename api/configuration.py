"""
PopPilot — paramètres SAISIS À LA MAIN (DAF / CDG) et référentiel des agences.

Ce routeur n'expose aucun calcul : il ouvre au web ce que `ingest/` et `socle/`
savent déjà écrire. Tout ce qu'il enregistre est un INTRANT de calcul, pas un
résultat — conformément au principe « stocker des faits datés, jamais un
indicateur calculé ».

CE QUI EST SAISI ICI, ET POURQUOI ÇA NE PEUT PAS ÊTRE CALCULÉ :

  1. TAUX DE CHANGE USD→CDF (§42). Le taux de clôture est publié par la BCC ;
     il ne se déduit d'aucune donnée du socle. Sans lui, aucun montant CDF n'est
     produit — le moteur REFUSE de convertir plutôt que de figer un taux, parce
     qu'un taux figé donne un bilan faux d'un facteur ~2268 sans lever d'alerte.

  2. PROVISION MANUELLE PAR AGENCE (note métier Goma). Le 1 %/mois cumulé de
     l'agence fermée est un prélèvement décidé par les comptables avec l'accord
     du DAF. L'outil l'ENREGISTRE, tracé et horodaté ; il ne le calcule pas, et
     le barème automatique ne s'applique plus à l'agence concernée (pas de
     double comptage).

  3. RÉINTÉGRATIONS FISCALES (§67). IBP = (résultat comptable + réintégrations)
     × taux. La grille vient du DAF : deux lignes sont amorcées (communication à
     50 %, dons au personnel à 100 %), elle reste à compléter.

  4. MAPPING BUDGÉTAIRE compte→ligne. Source : le fichier de SUIVI BUDGÉTAIRE
     (feuilles « Résultat charges » et « Résultat produits »), importable en un
     passage — et modifiable ligne à ligne ici, parce qu'un plan comptable bouge
     entre deux exercices et qu'attendre un ré-import complet pour rattacher un
     compte bloquerait le suivi.

  5. AGENCES. Ouvrir, fermer, suspendre, rouvrir. Une agence fermée garde un
     portefeuille réel et déclarable, mais n'a plus d'agents : son encours ne
     doit jamais être classé « orphelin » ni évalué en performance d'agents.

RÔLES : lecture pour les rôles à accès total (l'AUDIT doit pouvoir CONSTATER ce
qui a été saisi, et par qui) ; écriture réservée à DIRECTION / CDG, comme les
imports. Un contrôleur ne remplit pas ce qu'il contrôle.
"""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy import select

from auth_supabase import (ROLES_ACCES_TOTAL, ROLES_ECRITURE, exiger_role,
                           utilisateur_courant)
from ingest.provision_manuelle import (lister_provisions_manuelles,
                                       saisir_provision_manuelle)
from ingest.taux_change import saisir_taux
from ingest.import_budget import (affecter_compte, mapping_detaille,
                                  supprimer_affectation)
from socle.agences import ACTIVE, FERMEE, SUSPENDUE, enregistrer_agence
from socle.schema import (DimAgence, ParamReintegration, ParamTauxChange,
                          ParamTauxIBP, ProvisionManuelle, get_session)

routeur = APIRouter(tags=["configuration"])

STATUTS = (ACTIVE, FERMEE, SUSPENDUE)
SENS_VALIDES = ("charge", "produit")


def _date(valeur, champ: str) -> dt.date:
    try:
        return dt.date.fromisoformat(str(valeur))
    except (ValueError, TypeError):
        raise HTTPException(400, f"{champ} : date invalide ({valeur!r}), format AAAA-MM-JJ.")


def _montant(valeur, champ: str) -> float:
    try:
        return float(valeur)
    except (ValueError, TypeError):
        raise HTTPException(400, f"{champ} : montant invalide ({valeur!r}).")


def _exiger(corps: dict, champ: str):
    valeur = corps.get(champ)
    if valeur is None or (isinstance(valeur, str) and not valeur.strip()):
        raise HTTPException(422, f"Champ obligatoire manquant : {champ}.")
    return valeur


# ─────────────────────────────────────────────────────────────────────────────
# Vue d'ensemble d'un arrêté
# ─────────────────────────────────────────────────────────────────────────────
@routeur.get("/configuration/arrete")
def configuration_arrete(arrete: str, user: dict = Depends(utilisateur_courant)):
    """Tout ce qui est saisi à la main et qui pèse sur les calculs de cet arrêté.

    Le taux renvoyé est celui EN VIGUEUR (dernière date d'effet ≤ arrêté), et on
    dit s'il est du mois : un arrêté de décembre calculé avec le taux d'août
    passe sans erreur, pour des montants faux de quelques dixièmes de pour cent
    qu'on ne voit qu'au rapprochement.
    """
    exiger_role(user, ROLES_ACCES_TOTAL)
    d = _date(arrete, "arrete")
    s = get_session()
    try:
        taux = s.execute(
            select(ParamTauxChange.date_effet, ParamTauxChange.taux)
            .where(ParamTauxChange.date_effet <= d)
            .order_by(ParamTauxChange.date_effet.desc())
        ).first()
        historique = s.execute(
            select(ParamTauxChange.id, ParamTauxChange.date_effet, ParamTauxChange.taux)
            .order_by(ParamTauxChange.date_effet.desc())
        ).all()
        reintegrations = s.execute(
            select(ParamReintegration).where(ParamReintegration.date_effet <= d)
            .order_by(ParamReintegration.date_effet.desc())
        ).scalars().all()
        ibp = s.execute(
            select(ParamTauxIBP.taux).where(ParamTauxIBP.date_effet <= d)
            .order_by(ParamTauxIBP.date_effet.desc())
        ).scalars().first()
        agences = s.execute(select(DimAgence).order_by(DimAgence.code_agence)).scalars().all()
        noms_agences = [a.code_agence for a in agences]
    finally:
        s.close()

    #  Dernière date d'effet par nature : c'est ce que le moteur applique.
    grille: dict[str, dict] = {}
    for r in reintegrations:
        grille.setdefault(r.compte_ou_ligne, {
            "id": r.id,
            "compte_ou_ligne": r.compte_ou_ligne,
            "taux_reintegration": r.taux_reintegration,
            "date_effet": r.date_effet,
        })

    return {
        "arrete": d,
        "taux_change": None if taux is None else {
            "date_effet": taux[0],
            "taux": taux[1],
            "du_mois_de_l_arrete": (taux[0].year, taux[0].month) == (d.year, d.month),
        },
        "taux_historique": [
            {"id": i, "date_effet": de, "taux": t} for i, de, t in historique
        ],
        "provisions_manuelles": lister_provisions_manuelles(d),
        "reintegrations": sorted(grille.values(), key=lambda r: r["compte_ou_ligne"]),
        "taux_ibp": ibp,
        "agences": noms_agences,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Taux de change
# ─────────────────────────────────────────────────────────────────────────────
@routeur.post("/configuration/taux")
def poser_taux(corps: dict = Body(...), user: dict = Depends(utilisateur_courant)):
    """Saisit le taux USD→CDF à une date d'effet. Idempotent sur la date."""
    exiger_role(user, ROLES_ECRITURE)
    date_effet = _date(_exiger(corps, "date_effet"), "date_effet")
    taux = _montant(_exiger(corps, "taux"), "taux")
    if taux <= 0:
        raise HTTPException(422, "Le taux doit être strictement positif.")
    return saisir_taux(date_effet, taux)


# ─────────────────────────────────────────────────────────────────────────────
# Provisions manuelles par agence
# ─────────────────────────────────────────────────────────────────────────────
@routeur.post("/configuration/provision-manuelle")
def poser_provision(corps: dict = Body(...), user: dict = Depends(utilisateur_courant)):
    """Enregistre la provision manuelle d'une agence pour un arrêté (idempotent).

    Le montant saisi REMPLACE le barème automatique pour cette agence : c'est
    voulu, et c'est ce qui évite le double comptage (cf. engine/derivation.py).
    """
    exiger_role(user, ROLES_ECRITURE)
    date_arrete = _date(_exiger(corps, "date_arrete"), "date_arrete")
    agence = str(_exiger(corps, "agence")).strip()
    montant = _montant(_exiger(corps, "montant"), "montant")
    if montant < 0:
        raise HTTPException(422, "Une provision ne peut pas être négative.")
    return saisir_provision_manuelle(
        date_arrete, agence, montant,
        note=str(corps.get("note") or "").strip(),
        #  Tracé au login réel, jamais à une valeur fournie par l'appelant :
        #  une saisie DAF doit pouvoir être attribuée sans discussion.
        saisi_par=user.get("login") or user.get("role") or "inconnu",
    )


@routeur.delete("/configuration/provision-manuelle")
def retirer_provision(arrete: str, agence: str,
                      user: dict = Depends(utilisateur_courant)):
    """Retire la provision manuelle d'une agence : le barème automatique reprend."""
    exiger_role(user, ROLES_ECRITURE)
    d = _date(arrete, "arrete")
    s = get_session()
    try:
        n = s.query(ProvisionManuelle).filter(
            ProvisionManuelle.date_arrete == d,
            ProvisionManuelle.agence == agence).delete()
        s.commit()
    finally:
        s.close()
    if n == 0:
        raise HTTPException(404, f"Aucune provision manuelle pour {agence} au {d}.")
    return {"supprimees": n, "agence": agence, "arrete": d,
            "effet": "le barème automatique s'applique de nouveau à cette agence"}


# ─────────────────────────────────────────────────────────────────────────────
# Réintégrations fiscales (§67)
# ─────────────────────────────────────────────────────────────────────────────
@routeur.post("/configuration/reintegration")
def poser_reintegration(corps: dict = Body(...), user: dict = Depends(utilisateur_courant)):
    """Ajoute ou met à jour une nature de charge réintégrée, à date d'effet."""
    exiger_role(user, ROLES_ECRITURE)
    date_effet = _date(_exiger(corps, "date_effet"), "date_effet")
    nature = str(_exiger(corps, "compte_ou_ligne")).strip()
    taux = _montant(_exiger(corps, "taux_reintegration"), "taux_reintegration")
    if not 0 <= taux <= 1:
        raise HTTPException(
            422, "Le taux de réintégration est une FRACTION entre 0 et 1 "
                 "(0,5 = 50 %). Une valeur en pourcentage multiplierait l'IBP par 100.")
    s = get_session()
    try:
        ligne = s.execute(
            select(ParamReintegration).where(
                ParamReintegration.compte_ou_ligne == nature,
                ParamReintegration.date_effet == date_effet)
        ).scalar_one_or_none()
        if ligne is None:
            ligne = ParamReintegration(compte_ou_ligne=nature, date_effet=date_effet)
            s.add(ligne)
        ligne.taux_reintegration = taux
        s.commit()
    finally:
        s.close()
    return {"compte_ou_ligne": nature, "taux_reintegration": taux, "date_effet": date_effet}


@routeur.delete("/configuration/reintegration")
def retirer_reintegration(compte_ou_ligne: str, date_effet: str | None = None,
                          user: dict = Depends(utilisateur_courant)):
    exiger_role(user, ROLES_ECRITURE)
    s = get_session()
    try:
        q = s.query(ParamReintegration).filter(
            ParamReintegration.compte_ou_ligne == compte_ou_ligne)
        if date_effet:
            q = q.filter(ParamReintegration.date_effet == _date(date_effet, "date_effet"))
        n = q.delete()
        s.commit()
    finally:
        s.close()
    if n == 0:
        raise HTTPException(404, f"Aucune réintégration nommée {compte_ou_ligne!r}.")
    return {"supprimees": n, "compte_ou_ligne": compte_ou_ligne}


# ─────────────────────────────────────────────────────────────────────────────
# Mapping budgétaire (saisie manuelle ; l'import de masse passe par /import)
# ─────────────────────────────────────────────────────────────────────────────
@routeur.get("/configuration/mapping-budget")
def lire_mapping_budget(user: dict = Depends(utilisateur_courant)):
    """Mapping EN VIGUEUR, tel que le moteur l'applique (dernière date d'effet)."""
    exiger_role(user, ROLES_ACCES_TOTAL)
    lignes = mapping_detaille()
    return {
        "lignes": lignes,
        "nb_comptes": len(lignes),
        "nb_charges": sum(1 for l in lignes if l["sens"] == "charge"),
        "nb_produits": sum(1 for l in lignes if l["sens"] == "produit"),
        "source": "fichier de suivi budgétaire — feuilles « Résultat charges » "
                  "et « Résultat produits » (import « budget_mapping »), "
                  "complété à la main ici.",
    }


@routeur.post("/configuration/mapping-budget")
def poser_mapping_budget(corps: dict = Body(...), user: dict = Depends(utilisateur_courant)):
    """Affecte (ou réaffecte) un compte à une ligne budgétaire."""
    exiger_role(user, ROLES_ECRITURE)
    compte = str(_exiger(corps, "numero_compte")).strip()
    ligne = str(_exiger(corps, "ligne_budgetaire")).strip()
    sens = str(_exiger(corps, "sens")).strip().lower()
    if sens not in SENS_VALIDES:
        raise HTTPException(422, f"sens doit valoir {' ou '.join(SENS_VALIDES)}.")
    date_effet = _date(corps["date_effet"], "date_effet") if corps.get("date_effet") else None
    return affecter_compte(compte, ligne, sens, date_effet=date_effet)


@routeur.delete("/configuration/mapping-budget")
def retirer_mapping_budget(numero_compte: str, date_effet: str | None = None,
                           user: dict = Depends(utilisateur_courant)):
    exiger_role(user, ROLES_ECRITURE)
    d = _date(date_effet, "date_effet") if date_effet else None
    r = supprimer_affectation(numero_compte, date_effet=d)
    if r["supprimees"] == 0:
        raise HTTPException(404, f"Le compte {numero_compte} n'est affecté à aucune ligne.")
    return r


# ─────────────────────────────────────────────────────────────────────────────
# Agences — ouvrir, fermer, suspendre, rouvrir
# ─────────────────────────────────────────────────────────────────────────────
@routeur.get("/agences")
def lister_agences(user: dict = Depends(utilisateur_courant)):
    """Référentiel des agences. Un rôle AGENCE ne voit que la sienne."""
    exiger_role(user, ROLES_ACCES_TOTAL | {"AGENCE"})
    s = get_session()
    try:
        agences = s.execute(select(DimAgence).order_by(DimAgence.code_agence)).scalars().all()
        lignes = [{
            "code_agence": a.code_agence, "nom": a.nom, "region": a.region,
            "statut": a.statut or ACTIVE, "date_ouverture": a.date_ouverture,
            "date_fermeture": a.date_fermeture, "motif": a.motif,
        } for a in agences]
    finally:
        s.close()
    if user["role"] not in ROLES_ACCES_TOTAL:
        sienne = (user.get("agence") or "").strip().upper()
        lignes = [l for l in lignes if (l["code_agence"] or "").strip().upper() == sienne]
    return {"agences": lignes, "statuts": list(STATUTS)}


@routeur.post("/agences")
def enregistrer_une_agence(corps: dict = Body(...), user: dict = Depends(utilisateur_courant)):
    """Crée une agence, ou modifie UNIQUEMENT les champs fournis.

    Fermer une agence n'efface ni son nom, ni sa région, ni sa date d'ouverture :
    son portefeuille reste déclarable à la BCC, et perdre son référentiel au
    moment précis où on la ferme serait le pire moment (cf. socle/agences.py).

    Une agence remise en ACTIVE voit sa date de fermeture et son motif effacés —
    sinon elle traînerait indéfiniment la trace d'une fermeture révolue.
    """
    exiger_role(user, ROLES_ECRITURE)
    code = str(_exiger(corps, "code_agence")).strip()

    champs: dict = {}
    for champ in ("nom", "region", "motif"):
        if champ in corps:
            valeur = corps[champ]
            champs[champ] = None if valeur is None else str(valeur).strip() or None
    for champ in ("date_ouverture", "date_fermeture"):
        if champ in corps:
            valeur = corps[champ]
            champs[champ] = _date(valeur, champ) if valeur else None

    if "statut" in corps:
        statut = str(corps["statut"] or "").strip().upper()
        if statut not in STATUTS:
            raise HTTPException(422, f"statut doit valoir {', '.join(STATUTS)}.")
        champs["statut"] = statut
        if statut == FERMEE and not champs.get("date_fermeture"):
            raise HTTPException(
                422, "Fermer une agence exige sa date de fermeture : le portefeuille "
                     "gelé se suit à partir de cette date.")
        if statut == ACTIVE:
            champs["date_fermeture"] = None
            champs["motif"] = None

    s = get_session()
    try:
        a = enregistrer_agence(s, code, **champs)
        resultat = {
            "code_agence": a.code_agence, "nom": a.nom, "region": a.region,
            "statut": a.statut, "date_ouverture": a.date_ouverture,
            "date_fermeture": a.date_fermeture, "motif": a.motif,
        }
    finally:
        s.close()
    return resultat
