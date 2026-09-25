"""
PopPilot API — primes (chantier 4) : toutes catégories, dont « AC et SUP ».

  GET  /primes/direction?arrete=…        chefs d'agence, adjoints, direction générale
  POST /primes/support                   fonctions support (effectifs saisis par agence)
  POST /primes/recouvrement  (multipart) agents + responsable recouvrement
  POST /primes/superviseurs-epargne (multipart) Agence | Cible | Réalisation | % + MOIS
  GET  /primes/superviseurs-epargne?mois=AAAA-MM   collecte déjà importée pour ce mois
  GET  /primes/ac-sup?arrete=…           agents de crédit et superviseurs (roster + épargne du mois)

Les calculs sont ceux de engine/moteur_primes.py via engine/primes_categories.py. Ces
endpoints CALCULENT ; seul le fichier de collecte d'épargne est CONSERVÉ (fait_collecte_epargne,
rangé à son mois : un fait daté, la prime se recalcule). Le figeage d'une campagne (fait_prime +
campagne_prime) est une action distincte, à valider par la Direction.

Accès : rôles à accès total (DIRECTION, CDG, AUDIT). Les primes sont nominatives et
institutionnelles : un rôle AGENCE n'y a pas accès (403), même pour sa propre agence.
"""
from __future__ import annotations

import datetime as dt
import os
import shutil
import tempfile

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from openpyxl.utils.exceptions import InvalidFileException
from pydantic import BaseModel, Field

from engine.primes_categories import (TAUX_DIRECTION_AGENCE, TAUX_DIRECTION_GENERALE,
                                      bases_support, lire_fichier_epargne_superviseurs,
                                      lire_fichier_recouvrement, primes_direction_agences,
                                      primes_direction_generale, primes_recouvrement,
                                      primes_superviseurs_epargne, primes_support)

from auth_supabase import ROLES_ACCES_TOTAL, exiger_role, utilisateur_courant
from import_cbs import _ecrire_sur_disque, _nom_sain

routeur = APIRouter(tags=["primes"])

# Base visée : celle de la plateforme (Supabase si DATABASE_URL). Les tests la remplacent.
from socle.schema import BASE_PAR_DEFAUT  # noqa: E402
BASE = BASE_PAR_DEFAUT


def _mois(m: str) -> dt.date:
    """« 2026-05 » (ou une date complète) → dernier jour du mois."""
    import calendar
    try:
        d = dt.date.fromisoformat(m if len(m) > 7 else f"{m}-01")
    except (TypeError, ValueError):
        raise HTTPException(422, f"Mois invalide : {m} (format attendu AAAA-MM)")
    return d.replace(day=calendar.monthrange(d.year, d.month)[1])


def _d(s: str) -> dt.date:
    try:
        return dt.date.fromisoformat(s)
    except ValueError:
        raise HTTPException(422, f"Date invalide : {s} (format attendu AAAA-MM-JJ)")


@routeur.get("/primes/direction")
def endpoint_primes_direction(arrete: str = Query(..., description="Date d'arrêté AAAA-MM-JJ"),
                              user: dict = Depends(utilisateur_courant)):
    """% du résultat comptable (compte de résultat par agence importé)."""
    exiger_role(user, ROLES_ACCES_TOTAL)
    from engine.primes_categories import resultats_agences_depuis_base
    res = resultats_agences_depuis_base(_d(arrete))
    total = round(sum(res.values()), 2)
    return {"arrete": arrete,
            "taux": {"agence": TAUX_DIRECTION_AGENCE, "direction_generale": TAUX_DIRECTION_GENERALE},
            "agences": primes_direction_agences(res),
            "direction_generale": primes_direction_generale(total)}


class DemandeSupport(BaseModel):
    arrete: str
    effectifs: dict[str, int] = Field(default_factory=dict,
                                      description="{agence: nombre d'agents support}")


@routeur.post("/primes/support")
def endpoint_primes_support(demande: DemandeSupport, user: dict = Depends(utilisateur_courant)):
    """Même montant pour chaque agent support d'une agence, selon les réalisations de l'agence."""
    exiger_role(user, ROLES_ACCES_TOTAL)
    if any(v < 0 for v in demande.effectifs.values()):
        raise HTTPException(422, "Un effectif ne peut pas être négatif.")
    b = bases_support(_d(demande.arrete), demande.effectifs)
    r = primes_support(b["agences"])
    return {"arrete": demande.arrete, "date_effet_objectifs": b["date_effet_objectifs"],
            "taux_change": b["taux_change"], "alertes": b["alertes"],
            "bareme": {"decaissement_atteint": 5, "epargne_60pct_encours": 10,
                       "par30": "≤3% → 30 ; 3-5% → 20 ; 5-7% → 10 ; >7% → 0"}, **r}


@routeur.post("/primes/recouvrement")
def endpoint_primes_recouvrement(fichier: UploadFile = File(...),
                                 feuille: str | None = Form(None),
                                 user: dict = Depends(utilisateur_courant)):
    """Fichier « Équipe | Agent | Agence | Montant 91-180 | Montant 181+ | Montant Radié »."""
    exiger_role(user, ROLES_ACCES_TOTAL)
    nom = _nom_sain(fichier.filename, (".xlsx", ".xlsm"))
    dossier = tempfile.mkdtemp(prefix="recouv_")
    try:
        chemin = os.path.join(dossier, nom)
        _ecrire_sur_disque(fichier, chemin)
        try:
            lu = lire_fichier_recouvrement(chemin, feuille)
        except (InvalidFileException, ValueError, StopIteration) as e:
            raise HTTPException(400, f"Fichier de recouvrement illisible : {e}")
    finally:
        shutil.rmtree(dossier, ignore_errors=True)
    if not lu["lignes"]:
        raise HTTPException(400, "Aucun agent trouvé sous l'en-tête du fichier.")
    return {"fichier": nom,
            "taux": {"agent": "91-180 : 1 % ; 181-360 : 3 % ; radié : 5 %",
                     "responsable": "91-180 : 0,3 % ; 181-360 : 0,5 % ; radié : 1 % (sur le total)"},
            **primes_recouvrement(lu["lignes"], lu["total_fichier"])}


@routeur.post("/primes/superviseurs-epargne")
def endpoint_primes_superviseurs_epargne(fichier: UploadFile = File(...),
                                         mois: str = Form(..., description="Mois concerné AAAA-MM"),
                                         feuille: str | None = Form(None),
                                         user: dict = Depends(utilisateur_courant)):
    """Collecte d'épargne du MOIS (Agence | Cible | Réalisation) : conservée, puis palier sur
    la réalisation totale. Ré-importer un mois remplace sa collecte (jamais de doublon)."""
    exiger_role(user, ROLES_ACCES_TOTAL)
    date_arrete = _mois(mois)
    nom = _nom_sain(fichier.filename, (".xlsx", ".xlsm"))
    dossier = tempfile.mkdtemp(prefix="epsup_")
    try:
        chemin = os.path.join(dossier, nom)
        _ecrire_sur_disque(fichier, chemin)
        try:
            lu = lire_fichier_epargne_superviseurs(chemin, feuille)
        except (InvalidFileException, ValueError, StopIteration) as e:
            raise HTTPException(400, f"Fichier épargne superviseurs illisible : {e}")
    finally:
        shutil.rmtree(dossier, ignore_errors=True)
    if not lu["lignes"]:
        raise HTTPException(400, "Aucune agence trouvée sous l'en-tête du fichier.")
    from socle.schema import FaitCollecteEpargne, get_session
    s = get_session(BASE)
    try:
        remplaces = s.query(FaitCollecteEpargne).filter(
            FaitCollecteEpargne.date_arrete == date_arrete).delete()
        for l in lu["lignes"]:
            s.add(FaitCollecteEpargne(date_arrete=date_arrete, agence=l["agence"], cible=l["cible"],
                                      realisation=l["realisation"], fichier=nom,
                                      importe_par=user.get("login") or user.get("email")))
        s.commit()
    finally:
        s.close()
    return {"fichier": nom, "mois": date_arrete.strftime("%Y-%m"),
            "date_arrete": date_arrete.isoformat(), "remplaces": remplaces,
            **primes_superviseurs_epargne(lu["lignes"], lu["total_fichier"])}


@routeur.get("/primes/superviseurs-epargne")
def endpoint_collecte_epargne(mois: str | None = Query(None, description="AAAA-MM (défaut : le plus récent)"),
                              user: dict = Depends(utilisateur_courant)):
    """Collecte déjà importée : la prime d'un mois se relit sans re-téléverser le fichier."""
    exiger_role(user, ROLES_ACCES_TOTAL)
    from sqlalchemy import select
    from socle.schema import FaitCollecteEpargne, get_session
    s = get_session(BASE)
    try:
        mois_dispo = sorted({d for (d,) in s.execute(
            select(FaitCollecteEpargne.date_arrete).distinct())}, reverse=True)
        cible = _mois(mois) if mois else (mois_dispo[0] if mois_dispo else None)
        lignes = s.execute(select(FaitCollecteEpargne).where(
            FaitCollecteEpargne.date_arrete == cible)).scalars().all() if cible else []
        donnees = [{"agence": l.agence, "cible": l.cible or 0.0, "realisation": l.realisation or 0.0,
                    "taux": (l.realisation / l.cible) if l.cible else None} for l in lignes]
        fichier = lignes[0].fichier if lignes else None
    finally:
        s.close()
    if not donnees:
        raise HTTPException(404, f"Aucune collecte d'épargne importée pour {mois or 'aucun mois'}.")
    return {"fichier": fichier, "mois": cible.strftime("%Y-%m"), "date_arrete": cible.isoformat(),
            "mois_disponibles": [d.strftime("%Y-%m") for d in mois_dispo],
            **primes_superviseurs_epargne(donnees)}


@routeur.get("/primes/ac-sup")
def endpoint_primes_ac_sup(arrete: str = Query(..., description="Arrêté du mois AAAA-MM-JJ"),
                           user: dict = Depends(utilisateur_courant)):
    """Primes des agents de crédit et superviseurs du mois (cascade CALCUL_PRIMES « AC et SUP »).
    Bloquant, jamais approximatif : roster + objectifs du mois et inventaire épargne requis."""
    exiger_role(user, ROLES_ACCES_TOTAL)
    from engine.primes_ac_sup import primes_ac_sup
    return primes_ac_sup(_d(arrete), db_path=BASE)
