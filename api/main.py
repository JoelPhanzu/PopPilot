"""
PopPilot — API FastAPI qui EXPOSE les moteurs Python validés.
Ne réécrit AUCUN calcul : importe engine/, socle/, ingest/ tels quels.
Connexion base : variable DATABASE_URL (Supabase) — cf. socle/schema.py.

Lancer en local :  uvicorn main:app --reload
"""
from __future__ import annotations
import datetime as dt
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# moteurs validés (noms de dossiers = engine, socle, ingest)
from engine.par import calculer_par
from engine.derivation import deriver_provisions, croissance_portefeuille
from engine.migrations import analyser_migrations
from engine.decaissement import decaissements
from engine.etats_financiers import etats_financiers
from engine.indicateurs import indicateurs_prudentiels
from engine.epargne import synthese_epargne, nb_epargnants

app = FastAPI(title="PopPilot API", version="1.0",
              description="Expose les moteurs de pilotage MICROPOP (validés au centime).")

# CORS : autoriser le front Next.js (adapter l'origine en production)
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
def endpoint_par(arrete: str = Query(..., description="Date d'arrêté AAAA-MM-JJ")):
    """PAR (global + par agence) à une date d'arrêté. Source unique : le crédit."""
    r = calculer_par(_d(arrete))
    g = r["global"]
    return {
        "arrete": arrete,
        "global": {"encours": g.encours, "par1": g.par1, "par30": g.par30, "par90": g.par90,
                   "pct_par1": g.pct_par1, "pct_par30": g.pct_par30, "pct_par90": g.pct_par90,
                   "nb_credits": g.nb_credits, "nb_clients": g.nb_clients},
        "agences": [{"agence": a.designation, "encours": a.encours, "par1": a.par1,
                     "par30": a.par30, "pct_par30": a.pct_par30} for a in r["agences"]],
    }


@app.get("/provisions")
def endpoint_provisions(arrete: str):
    return deriver_provisions(_d(arrete))


@app.get("/migrations")
def endpoint_migrations(arrete: str, precedent: str):
    return analyser_migrations(_d(arrete), _d(precedent))


@app.get("/croissance")
def endpoint_croissance(arrete: str, precedent: str):
    return croissance_portefeuille(_d(arrete), _d(precedent))


@app.get("/decaissements")
def endpoint_decaissements(arrete: str, debut: str, fin: str):
    return decaissements(_d(arrete), _d(debut), _d(fin))


@app.get("/etats-financiers")
def endpoint_etats(arrete: str):
    return etats_financiers(_d(arrete))


@app.get("/indicateurs")
def endpoint_indicateurs(arrete: str):
    return indicateurs_prudentiels(_d(arrete))


@app.get("/epargne")
def endpoint_epargne(arrete: str):
    s = synthese_epargne(_d(arrete))
    s["nb_epargnants"] = nb_epargnants(_d(arrete))
    return s
