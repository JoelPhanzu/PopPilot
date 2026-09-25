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
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Query, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from socle.schema import cible_base, env_encore_gabarit   # charge api/.env au passage
from engine.par import calculer_par
from engine.derivation import deriver_provisions, croissance_portefeuille
from engine.migrations import analyser_migrations
from engine.decaissement import decaissements
from engine.etats_financiers import etats_financiers
from engine.etats_detail import etats_detailles
from engine.indicateurs import indicateurs_prudentiels
from engine.epargne import synthese_epargne, nb_epargnants
from engine.budget import suivi_budgetaire

from auth_supabase import (utilisateur_courant, filtrer_par_agence,
                           exiger_role, ROLES_ACCES_TOTAL)
from import_cbs import routeur as routeur_import
from configuration import routeur as routeur_configuration
from export_excel import routeur as routeur_export
from rapports import routeur as routeur_rapports
from filtres_credit import routeur as routeur_filtres_credit
from sage import routeur as routeur_sage
from primes import routeur as routeur_primes
from compte_resultat import routeur as routeur_compte_resultat
from productivite import routeur as routeur_productivite
from eljo import routeur as routeur_eljo
from archives import routeur as routeur_archives
from epargne_tdb import routeur as routeur_epargne_tdb
from export_tableaux import routeur as routeur_export_tableaux
from arretes import routeur as routeur_arretes
from taux import routeur as routeur_taux

@asynccontextmanager
async def _cycle_de_vie(_app: FastAPI):
    """Au démarrage : annoncer la base réellement visée et l'état du secret JWT.
    Une API qui tourne sur le repli SQLite sortirait des chiffres d'une base vide,
    sans erreur visible — d'où cet avertissement explicite."""
    print(f"[PopPilot] Base cible : {cible_base()}")
    gabarit = env_encore_gabarit()
    if gabarit:
        print(f"[PopPilot] ATTENTION : {gabarit}")
    if not os.environ.get("DATABASE_URL"):
        print("[PopPilot] ATTENTION : DATABASE_URL absente → repli SQLite local (base vide). "
              "Renseigner api/.env avant de lire le moindre chiffre.")
    # Un seul des deux régimes de signature suffit : clés publiques du projet
    # (JWKS, via SUPABASE_URL) OU secret partagé hérité. Avertir sur le secret
    # seul ferait passer pour mal configurée une API parfaitement fonctionnelle.
    from auth_supabase import url_supabase
    if url_supabase():
        print(f"[PopPilot] Jetons vérifiés via les clés publiques : "
              f"{url_supabase()}/auth/v1/.well-known/jwks.json")
    elif os.environ.get("SUPABASE_JWT_SECRET"):
        print("[PopPilot] Jetons vérifiés via le secret partagé hérité (HS256). "
              "Un projet migré vers les clés de signature émet de l'ES256 : "
              "renseigner SUPABASE_URL dans api/.env.")
    else:
        print("[PopPilot] ATTENTION : ni SUPABASE_URL ni SUPABASE_JWT_SECRET → "
              "les endpoints authentifiés renverront 500.")
    yield


app = FastAPI(title="PopPilot API", version="1.0",
              description="Expose les moteurs de pilotage MICROPOP (validés au centime).",
              lifespan=_cycle_de_vie)

app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])

# Import des fichiers du CBS depuis le web (POST /import/{domaine}, GET /imports).
# Endpoints définis dans import_cbs.py : ils exposent ingest/ sans en réécrire un calcul.
app.include_router(routeur_import)

# Parametres saisis a la main (taux, provisions, reintegrations, mapping) et
# referentiel des agences. Aucun calcul : ces endpoints ouvrent au web ce que
# ingest/ et socle/ savent deja ecrire.
app.include_router(routeur_configuration)

# Export Excel des tableaux de bord. Appelle les MEMES moteurs que les ecrans :
# ce qui est exporte est ce qui est affiche, au cloisonnement pres.
app.include_router(routeur_export)

# Rapports reglementaires BCC (FINA, AML/LBC-FT, systeme de paiement).
# Ne touchent PAS au socle : une generation le lit, elle ne l'ecrit pas.
app.include_router(routeur_rapports)

# Tableau de bord credit FILTRE (agence, sexe, produit, duree, client, agent,
# superviseur). Enchaine moteur_filtres + les moteurs PAR/provisions existants.
app.include_router(routeur_filtres_credit)

# Grand livre CBS -> fichier SAGE (taux journalier de la plateforme). Enchaine
# engine/traitement_sage ; journalise dans journal_sage_traite.
app.include_router(routeur_sage)

# Primes hors « AC et SUP » : direction, fonctions support, recouvrement.
# Calculent via engine/moteur_primes ; n'ecrivent rien.
app.include_router(routeur_primes)

# Compte d'exploitation par agence (lecture du fichier du CDG importe). Cloisonne.
app.include_router(routeur_compte_resultat)

# Productivite (interets encaisses, encours, PAR, decaissements) par agent/sup/agence.
app.include_router(routeur_productivite)

# Eljo Smart : questions en langage naturel -> moteurs valides. Trace eljo_conversation.
app.include_router(routeur_eljo)

# Archives : bibliotheque versionnee, edition en ligne tracee, series temporelles.
app.include_router(routeur_archives)

# Tableau de bord epargne : stocks, flux par mois, couverture epargne / credit, Top N.
app.include_router(routeur_epargne_tdb)

# Arretes enregistres par domaine : le calendrier affiche le dernier arrete <= date choisie.
app.include_router(routeur_arretes)

# Taux de change : consultation chronologique filtree + export CSV / Excel / PDF.
app.include_router(routeur_taux)

# Export des tableaux de bord tels qu'affiches (CSV / Excel) ; le PDF se fait depuis l'ecran.
app.include_router(routeur_export_tableaux)


@app.exception_handler(ValueError)
def _donnee_absente(_request: Request, exc: ValueError):
    """Traduit les ValueError des moteurs en 404 explicite.

    POURQUOI : les moteurs signalent une periode non chargee par
    `raise ValueError("Aucun pret pour l'arrete ...")`. Sans ce gestionnaire,
    FastAPI renvoie un 500 "Internal Server Error" nu : l'appelant croit a une
    panne de l'API alors que la donnee n'est simplement pas importee, et le
    message utile du moteur reste enterre dans les logs du serveur.
    404 = la ressource demandee (cet arrete) n'existe pas encore.
    """
    return JSONResponse(status_code=404, content={"detail": str(exc)})


def _d(s: str) -> dt.date:
    try:
        return dt.date.fromisoformat(s)
    except ValueError:
        raise HTTPException(400, f"Date invalide : {s} (format attendu AAAA-MM-JJ)")


@app.get("/")
def racine():
    return {"service": "PopPilot API", "statut": "ok",
            "message": "Moteurs de pilotage MICROPOP. Voir /docs pour les endpoints."}


@app.get("/sante")
def sante():
    """Diagnostic de configuration (aucun secret n'est renvoye).

    A appeler EN PREMIER apres deploiement : si base_cible dit "SQLite local (repli)",
    l'API ne parle PAS a Supabase et tous les chiffres seraient ceux d'une base vide.
    """
    # Un .env encore au gabarit ne compte PAS comme configure : sinon /sante
    # annoncerait "supabase_connectee: true" avec une URL qui ne resout meme pas.
    gabarit = env_encore_gabarit()
    from auth_supabase import url_supabase
    origine = url_supabase()
    return {
        "base_cible": cible_base(),
        "supabase_connectee": bool(os.environ.get("DATABASE_URL")) and not gabarit,
        # Deux regimes de signature : cles publiques (JWKS, projets recents) ou
        # secret partage herite. Il en faut AU MOINS un, sinon aucun jeton ne
        # peut etre verifie et tous les endpoints repondent 500.
        "jwt_cles_publiques": f"{origine}/auth/v1/.well-known/jwks.json" if origine else None,
        "jwt_secret_herite": bool(os.environ.get("SUPABASE_JWT_SECRET")) and not gabarit,
        "jwt_configure": (bool(origine)
                          or (bool(os.environ.get("SUPABASE_JWT_SECRET")) and not gabarit)),
        "a_corriger": gabarit,
    }


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
    """Décaissements sur [début ; fin]. Cloisonné : une agence ne voit QUE son agence.

    Le détail par agence était bien filtré, mais le bloc « global » restait celui de
    toute l'institution : un responsable d'agence lisait donc le volume décaissé de
    MICROPOP entier. Pour un rôle AGENCE, le « global » est désormais recalculé sur
    sa seule agence — jamais une somme qu'il n'a pas le droit de voir.
    """
    r = decaissements(_d(arrete), _d(debut), _d(fin))
    if user["role"] not in ROLES_ACCES_TOTAL:
        ag = user.get("agence")
        par_agence = {k: v for k, v in r.get("par_agence", {}).items() if k == ag}
        sienne = par_agence.get(ag, {"nombre": 0, "volume": 0.0})
        r["par_agence"] = par_agence
        r["global"] = {"nombre": sienne["nombre"], "volume": sienne["volume"]}
        r["portee"] = ag                      # dire explicitement ce que couvre le total
    else:
        r["portee"] = "MICROPOP"
    return r


@app.get("/etats-financiers")
def endpoint_etats(arrete: str, user: dict = Depends(utilisateur_courant)):
    exiger_role(user, ROLES_ACCES_TOTAL)
    return etats_financiers(_d(arrete))


@app.get("/etats-financiers/detail")
def endpoint_etats_detail(arrete: str, devise: str = "USD",
                          user: dict = Depends(utilisateur_courant)):
    """Bilan et compte de résultat au format INTÉGRAL du référentiel BCC.

    Les 32 lignes de l'actif, les 28 du passif, les 26 du compte de résultat —
    sous-totaux, soldes intermédiaires et lignes à zéro compris — chacune avec
    les comptes de balance qui la composent. `/etats-financiers` en reste au
    résumé par rubrique ; les deux doivent donner le même total général, et
    `controles.ecart_avec_agregat` le vérifie à chaque appel.
    """
    exiger_role(user, ROLES_ACCES_TOTAL)
    return etats_detailles(_d(arrete), devise=devise.strip().upper())


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


@app.get("/budget")
def endpoint_budget(arrete: str,
                    precedent: str | None = None,
                    hypothese: str = "H1",
                    user: dict = Depends(utilisateur_courant)):
    """Suivi budgétaire d'un arrêté : réalisé mensuel ET cumulé face au budget.

    L'exercice et le mois ne sont PAS des paramètres : ils se déduisent de l'arrêté
    (cf. engine.budget.suivi_budgetaire). Les recevoir à part permettrait de comparer
    le réalisé de juillet au budget de mars sans qu'aucun contrôle ne s'en aperçoive.

    Paramètres : `arrete` (AAAA-MM-JJ), `precedent` (arrêté de base du réalisé
    mensuel, déduit de la base s'il est omis), `hypothese` (défaut « H1 »).

    `precedent` reste fournissable à la main (rejouer un mois avec une autre base),
    mais son absence n'est pas une erreur : le moteur va chercher le dernier arrêté
    de l'exercice antérieur au mois, et DIT quand il n'en trouve pas — le niveau
    mensuel est alors déclaré indisponible au lieu d'afficher un cumul de plusieurs
    mois en face d'un budget d'un seul.
    """
    exiger_role(user, ROLES_ACCES_TOTAL)
    r = suivi_budgetaire(_d(arrete),
                         precedent=_d(precedent) if precedent else None,
                         hypothese=hypothese)
    # Dates en ISO : le front les affiche et les remet dans l'URL telles quelles.
    r["arrete"] = r["arrete"].isoformat()
    r["precedent"] = r["precedent"].isoformat() if r["precedent"] else None
    return r
