"""
PopPilot — API FastAPI qui EXPOSE les moteurs Python validés.
Ne réécrit AUCUN calcul : importe engine/, socle/, ingest/ tels quels.

SÉCURITÉ (écart 4) : chaque endpoint identifie l'appelant via son jeton Supabase
(auth_supabase.utilisateur_courant) et applique le cloisonnement par agence dans l'API,
car l'API se connecte à PostgreSQL en 'postgres' qui ignore le RLS.

Lancer en local :  uvicorn main:app --reload
"""
from __future__ import annotations
import datetime as dt
from fastapi import FastAPI, Query, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware

from engine.par import calculer_par
from engine.derivation import deriver_provisions, croissance_portefeuille
from engine.migrations import analyser_migrations
from engine.decaissement import decaissements
from engine.etats_financiers import etats_financiers
from engine.indicateurs import indicateurs_prudentiels
from engine.epargne import synthese_epargne, nb_epargnants

from auth_supabase import (utilisateur_courant, filtrer_par_agence,
                           exiger_role, ROLES_ACCES_TOTAL)

app = FastAPI(title="PopPilot API", version="1.0",
              description="Expose les moteurs de pilotage MICROPOP (validés au centime).")

app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])


def _d(s: str) -> dt.date:
    try:
        return dt.date.fromisoformat(s)
    except ValueError:
        raise HTTPException(400, f"Date invalide : {s} (format attendu AAAA-MM-JJ)")


@app.get("/")
def racine():
    return {"service": "PopPilot API", "statut": "ok",
            "message": "Moteurs de pilotage MICROPOP. Voir /docs pour les endpoints."}


@app.get("/par")
def endpoint_par(arrete: str = Query(..., description="Date d'arrêté AAAA-MM-JJ"),
                 user: dict = Depends(utilisateur_courant)):
    """PAR (global + par agence). Cloisonné : un rôle AGENCE ne voit que son agence."""
    r = calculer_par(_d(arrete))
    agences = [{"agence": a.designation, "encours": a.encours, "par1": a.par1,
                "par30": a.par30, "pct_par30": a.pct_par30} for a in r["agences"]]
    # FILTRE API par agence (écart 4)
    agences = filtrer_par_agence(user, agences)

    if user["role"] in ROLES_ACCES_TOTAL:
        g = r["global"]
        glob = {"encours": g.encours, "par1": g.par1, "par30": g.par30, "par90": g.par90,
                "pct_par1": g.pct_par1, "pct_par30": g.pct_par30, "pct_par90": g.pct_par90,
                "nb_credits": g.nb_credits, "nb_clients": g.nb_clients}
    else:
        # pour une agence, le "global" = sa seule agence
        a = agences[0] if agences else None
        glob = ({"encours": a["encours"], "par1": a["par1"], "par30": a["par30"],
                 "pct_par30": a["pct_par30"]} if a else {})
    return {"arrete": arrete, "role": user["role"], "global": glob, "agences": agences}


# Les endpoints ci-dessous renvoient des agrégats globaux (compta, indicateurs) :
# réservés aux rôles à accès total ; une agence n'y a pas accès.

@app.get("/provisions")
def endpoint_provisions(arrete: str, user: dict = Depends(utilisateur_courant)):
    exiger_role(user, ROLES_ACCES_TOTAL)
    return deriver_provisions(_d(arrete))


@app.get("/migrations")
def endpoint_migrations(arrete: str, precedent: str, user: dict = Depends(utilisateur_courant)):
    exiger_role(user, ROLES_ACCES_TOTAL)
    return analyser_migrations(_d(arrete), _d(precedent))


@app.get("/croissance")
def endpoint_croissance(arrete: str, precedent: str, user: dict = Depends(utilisateur_courant)):
    exiger_role(user, ROLES_ACCES_TOTAL)
    return croissance_portefeuille(_d(arrete), _d(precedent))


@app.get("/decaissements")
def endpoint_decaissements(arrete: str, debut: str, fin: str,
                           user: dict = Depends(utilisateur_courant)):
    r = decaissements(_d(arrete), _d(debut), _d(fin))
    if user["role"] not in ROLES_ACCES_TOTAL:
        # cloisonner : ne garder que l'agence de l'utilisateur
        ag = user.get("agence")
        r["par_agence"] = {k: v for k, v in r.get("par_agence", {}).items() if k == ag}
    return r


@app.get("/etats-financiers")
def endpoint_etats(arrete: str, user: dict = Depends(utilisateur_courant)):
    exiger_role(user, ROLES_ACCES_TOTAL)
    return etats_financiers(_d(arrete))


@app.get("/indicateurs")
def endpoint_indicateurs(arrete: str, user: dict = Depends(utilisateur_courant)):
    exiger_role(user, ROLES_ACCES_TOTAL)
    return indicateurs_prudentiels(_d(arrete))


@app.get("/epargne")
def endpoint_epargne(arrete: str, user: dict = Depends(utilisateur_courant)):
    exiger_role(user, ROLES_ACCES_TOTAL)
    s = synthese_epargne(_d(arrete))
    s["nb_epargnants"] = nb_epargnants(_d(arrete))
    return s
