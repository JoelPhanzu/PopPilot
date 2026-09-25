"""
PopPilot API — export des TABLEAUX DE BORD tels qu'affichés (CSV ou Excel).

  GET /export/tableau/credit    mêmes paramètres que GET /credit/tableau-de-bord
  GET /export/tableau/epargne   mêmes paramètres que GET /epargne/tableau-de-bord
  GET /export/tableau/clients   mêmes paramètres que GET /credit/clients-top
      + format=csv (défaut) | xlsx

Aucun calcul : ces exports APPELLENT les endpoints de l'écran (mêmes moteurs, même
cloisonnement, mêmes champs masqués pour un rôle AGENCE) puis écrivent leurs lignes. Un
fichier exporté est donc toujours identique à l'écran dont il vient.

CSV « à la française » : séparateur « ; », virgule décimale, UTF-8 avec BOM — il s'ouvre
tel quel dans Excel. Le PDF se fait depuis l'écran (impression du navigateur, mise en
page dédiée) : il reproduit exactement ce qu'on regarde, graphiques compris.
"""
from __future__ import annotations

import csv
import io

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from openpyxl import Workbook
from openpyxl.styles import Font

from auth_supabase import utilisateur_courant

routeur = APIRouter(tags=["export-tableaux"])

_CREDIT = [
    ("Agence", "agence"), ("Désignation", "designation"), ("Statut", "statut"),
    ("Agents", "nb_agents"), ("#P15 objectif", "p15_objectif"), ("#P15", "p15"),
    ("#Objectif décaissement", "objectif_nombre"), ("Nombre décaissé", "decaisse_nombre"),
    ("% réalisation (nombre)", "pct_realisation_nombre"), ("Productivité", "productivite"),
    ("Objectif volume", "objectif_volume"), ("Volume décaissé", "decaisse_volume"),
    ("% réalisation (volume)", "pct_realisation_volume"), ("Nombre de clients", "nb_clients"),
    ("Crédits", "nb_credits"), ("Encours", "encours"), ("Croissance", "croissance"),
    ("PAR1", "par1"), ("PAR30", "par30"), ("PAR90", "par90"), ("% PAR1", "pct_par1"),
    ("% PAR30", "pct_par30"), ("% PAR90", "pct_par90"), ("Provisions", "provisions"),
    ("Provisions M-1", "provisions_m1"), ("Variation de provision", "variation_provision"),
    ("Coût du risque", "cout_du_risque"), ("#Entrés dans la PAR", "entree_par_nb"),
    ("Entrés dans la PAR", "entree_par_montant"),
    ("Migration vers 31-60", ("migration_vers", "31-60")),
    ("Migration vers 61-90", ("migration_vers", "61-90")),
    ("Migration vers 91-180", ("migration_vers", "91-180")),
    ("Migration vers 181-360", ("migration_vers", "181-360")),
    ("Migration vers 361+", ("migration_vers", "361+")),
    ("Intérêts encaissés", "interets_encaisses"), ("Capital remboursé", "capital_rembourse"),
    ("Pénalités", "penalites_encaissees"), ("Recouvré sur PAR", "recouvre_sur_par"),
    ("Potentiel coût du risque", "potentiel_cout_du_risque"),
    ("#Potentiel migration", "potentiel_migration_nb"),
    ("Potentiel migration", "potentiel_migration_montant"),
    ("Encours M-1", "encours_m1"), ("#Clients M-1", "nb_clients_m1"), ("#Crédits M-1", "nb_credits_m1"),
]
_EPARGNE = [
    ("Désignation", "designation"), ("Comptes", "nb_comptes"),
    ("Comptes créditeurs", "nb_comptes_crediteurs"), ("Épargnants", "nb_epargnants"),
    ("Encours (USD)", "encours"), ("dont USD d'origine", "encours_usd_origine"),
    ("dont CDF d'origine", "encours_cdf_origine"), ("À vue (USD)", "a_vue"),
    ("À terme (USD)", "a_terme"), ("Obligatoire (USD)", "obligatoire"),
    ("Encours M-1", "encours_m1"), ("Croissance", "croissance"), ("Dépôts", "depots"),
    ("Retraits", "retraits"), ("Collecte nette", "collecte_nette"),
    ("#Comptes avec dépôt", "nb_depots"), ("#Comptes avec retrait", "nb_retraits"),
    ("Encours crédit", "encours_credit"), ("Couverture (épargne / crédit)", "couverture_credit"),
]
_CLIENTS = [
    ("Classement", "classement"), ("Rang", "rang"), ("N° client", "numero_client"),
    ("Client", "nom_client"), ("Agence", "agence"), ("Agent", "agent"),
    ("Valeur du critère", "valeur"), ("Encours", "encours"), ("Encours en retard", "encours_retard"),
    ("Jours de retard (max)", "max_jours_retard"), ("Crédits", "nb_credits"),
]


def _val(ligne: dict, cle):
    if isinstance(cle, tuple):
        return (ligne.get(cle[0]) or {}).get(cle[1])
    return ligne.get(cle)


def _csv(colonnes, lignes, entete: list[str]) -> bytes:
    tampon = io.StringIO()
    w = csv.writer(tampon, delimiter=";", lineterminator="\r\n")
    for texte in entete:
        w.writerow([texte])
    w.writerow([])
    w.writerow([t for t, _ in colonnes])
    for l in lignes:
        w.writerow(["" if (v := _val(l, c)) is None else
                    (f"{v:.2f}".replace(".", ",") if isinstance(v, float) else v)
                    for _, c in colonnes])
    return ("﻿" + tampon.getvalue()).encode("utf-8")


def _xlsx(colonnes, lignes, entete: list[str]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Tableau de bord"
    for texte in entete:
        ws.append([texte])
    ws.append([])
    ws.append([t for t, _ in colonnes])
    for cell in ws[ws.max_row]:
        cell.font = Font(bold=True)
    for l in lignes:
        ws.append([_val(l, c) for _, c in colonnes])
    tampon = io.BytesIO()
    wb.save(tampon)
    return tampon.getvalue()


def _fichier(colonnes, lignes, entete, nom: str, format: str) -> Response:
    if format == "xlsx":
        contenu, type_ = _xlsx(colonnes, lignes, entete), \
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
        contenu, type_ = _csv(colonnes, lignes, entete), "text/csv; charset=utf-8"
    nom = f"{nom}.{format}"
    return Response(content=contenu, media_type=type_, headers={
        "Content-Disposition": f"attachment; filename=\"{nom}\"", "Cache-Control": "no-store"})


def _format(format: str) -> str:
    if format not in ("csv", "xlsx"):
        raise HTTPException(422, f"format inconnu : {format} (attendu csv ou xlsx)")
    return format


def _entete(titre: str, r: dict, user: dict) -> list[str]:
    filtres = ", ".join(f"{k}={v}" for k, v in (r.get("filtres") or {}).items() if v) or "aucun"
    return [f"PopPilot — {titre}",
            f"Stocks au {r.get('arrete')} ; flux du {r.get('debut')} au {r.get('fin')} ; "
            f"niveau {r.get('niveau')} ; filtres : {filtres}",
            f"Exporté par {user.get('login') or user.get('email') or '?'} ({user['role']})"]


@routeur.get("/export/tableau/credit")
def export_tableau_credit(request: Request, format: str = Query("csv"),
                          user: dict = Depends(utilisateur_courant)):
    from filtres_credit import endpoint_tableau_de_bord
    q = request.query_params
    r = endpoint_tableau_de_bord(
        arrete=q.get("arrete") or "", debut=q.get("debut"), fin=q.get("fin"),
        precedent=q.get("precedent"), niveau=q.get("niveau") or "agence",
        limite=int(q.get("limite") or 100000), agence=q.get("agence"), sexe=q.get("sexe"),
        produits=q.getlist("produits") or None, duree=q.get("duree"), client=q.get("client"),
        agent=q.get("agent"), superviseur=q.get("superviseur"), user=user)
    return _fichier(_CREDIT, r["lignes"], _entete("tableau de bord crédit", r, user),
                    f"PopPilot_credit_{r['arrete']}_{r['niveau']}", _format(format))


@routeur.get("/export/tableau/epargne")
def export_tableau_epargne(request: Request, format: str = Query("csv"),
                           user: dict = Depends(utilisateur_courant)):
    from epargne_tdb import endpoint_tableau_de_bord_epargne
    q = request.query_params
    r = endpoint_tableau_de_bord_epargne(
        arrete=q.get("arrete"), debut=q.get("debut"), fin=q.get("fin"),
        niveau=q.get("niveau") or "agence", limite=int(q.get("limite") or 100000),
        agence=q.get("agence"), devise=q.get("devise"), type_depot=q.get("type_depot"),
        sexe=q.get("sexe"), groupe=q.get("groupe"), user=user)
    return _fichier(_EPARGNE, r["lignes"], _entete("tableau de bord épargne", r, user),
                    f"PopPilot_epargne_{r['arrete']}_{r['niveau']}", _format(format))


@routeur.get("/export/tableau/clients")
def export_tableau_clients(request: Request, format: str = Query("csv"),
                           user: dict = Depends(utilisateur_courant)):
    from filtres_credit import endpoint_clients_top
    q = request.query_params
    r = endpoint_clients_top(
        arrete=q.get("arrete") or "", n=int(q.get("n") or 10), critere=q.get("critere") or "encours",
        debut=q.get("debut"), fin=q.get("fin"), agence=q.get("agence"), sexe=q.get("sexe"),
        produits=q.getlist("produits") or None, duree=q.get("duree"), agent=q.get("agent"),
        superviseur=q.get("superviseur"), user=user)
    lignes = ([{**c, "classement": "meilleurs", "rang": i + 1} for i, c in enumerate(r["meilleurs"])]
              + [{**c, "classement": "pires", "rang": i + 1} for i, c in enumerate(r["pires"])])
    entete = [f"PopPilot — Top {r['n']} clients (meilleurs : {r['critere']} ; pires : encours en retard)",
              f"Arrêté {r['arrete']}", f"Exporté par {user.get('login') or '?'} ({user['role']})"]
    return _fichier(_CLIENTS, lignes, entete, f"PopPilot_top{r['n']}_clients_{r['arrete']}",
                    _format(format))
