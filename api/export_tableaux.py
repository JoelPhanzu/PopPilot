"""
PopPilot API — export des TABLEAUX tels qu'affichés (CSV, Excel ou PDF).

  GET /export/tableau/credit    mêmes paramètres que GET /credit/tableau-de-bord
  GET /export/tableau/epargne   mêmes paramètres que GET /epargne/tableau-de-bord
  GET /export/tableau/clients   mêmes paramètres que GET /credit/clients-top
      + format=csv (défaut) | xlsx | pdf
  POST /export/sections         tout autre tableau de l'interface (compte d'exploitation,
      productivité, primes, bilan, indicateurs, budget, journaux…) : l'écran envoie les
      lignes BRUTES qu'il affiche déjà (reçues de l'API, donc déjà cloisonnées), le serveur
      n'écrit que le fichier. Aucune valeur n'y est calculée.

Aucun calcul : ces exports APPELLENT les endpoints de l'écran (mêmes moteurs, même
cloisonnement, mêmes champs masqués pour un rôle AGENCE) puis écrivent leurs lignes. Un
fichier exporté est donc toujours identique à l'écran dont il vient.

CSV « à la française » : séparateur « ; », virgule décimale, UTF-8 avec BOM — il s'ouvre
tel quel dans Excel. PDF : tableau paginé (A4 paysage, en-têtes répétés, charte MICROPOP) ;
l'impression du navigateur reste disponible pour un écran avec ses graphiques.
"""
from __future__ import annotations

import csv
import io

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from openpyxl import Workbook
from openpyxl.styles import Font
from pydantic import BaseModel, Field

from auth_supabase import utilisateur_courant

routeur = APIRouter(tags=["export-tableaux"])

_CREDIT = [
    ("Agence", "agence"), ("Désignation", "designation"), ("Fonction", "fonction"),
    ("Statut", "statut"), ("Agents", "nb_agents"), ("#P15 objectif", "p15_objectif"), ("#P15", "p15"),
    ("% P15", lambda l: l["p15"] / l["p15_objectif"] if l.get("p15_objectif") else None),
    ("#Objectif décaissement", "objectif_nombre"), ("Nombre décaissé", "decaisse_nombre"),
    ("% réalisation (nombre)", "pct_realisation_nombre"), ("Productivité", "productivite"),
    ("Objectif volume", "objectif_volume"), ("Volume décaissé", "decaisse_volume"),
    ("% réalisation (volume)", "pct_realisation_volume"), ("Nombre de clients", "nb_clients"),
    ("Crédits", "nb_credits"), ("Encours", "encours"), ("Croissance", "croissance"),
    ("PAR1", "par1"), ("PAR30", "par30"), ("PAR90", "par90"), ("% PAR1", "pct_par1"),
    ("% PAR30", "pct_par30"), ("% PAR90", "pct_par90"), ("Provisions", "provisions"),
    ("% provisions", lambda l: l["provisions"] / l["encours"]
     if l.get("provisions") is not None and l.get("encours") else None),
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
    ("Désignation", "designation"), ("Nom du client", "nom_client"),
    ("Statut juridique", "statut_juridique"), ("Type de dépôt", "type_depot"), ("Devise", "devise"), ("Comptes", "nb_comptes"),
    ("Comptes créditeurs", "nb_comptes_crediteurs"), ("Épargnants", "nb_epargnants"),
    ("Encours (USD)", "encours"), ("dont USD d'origine", "encours_usd_origine"),
    ("dont CDF d'origine", "encours_cdf_origine"), ("À vue (USD)", "a_vue"),
    ("À terme (USD)", "a_terme"), ("Obligatoire (USD)", "obligatoire"),
    ("Encours M-1", "encours_m1"), ("Croissance", "croissance"), ("Dépôts", "depots"),
    ("Retraits", "retraits"), ("Collecte nette", "collecte_nette"),
    ("#Comptes avec dépôt", "nb_depots"), ("#Comptes avec retrait", "nb_retraits"),
    ("Encours crédit", "encours_credit"), ("Couverture (épargne / crédit)", "couverture_credit"),
]
_SANS_OBJET_EPARGNE = {
    "agence": ("nom_client", "statut_juridique", "type_depot", "devise"),
    "type": ("nom_client", "statut_juridique", "type_depot", "devise", "encours_credit", "couverture_credit"),
    "produit": ("nom_client", "statut_juridique", "encours_credit", "couverture_credit"),
    "client": ("type_depot", "devise"),
}
_CLIENTS = [
    ("Classement", "classement"), ("Rang", "rang"), ("N° client", "numero_client"),
    ("Client", "nom_client"), ("Agence", "agence"), ("Agent", "agent"),
    ("Valeur du critère", "valeur"), ("Encours", "encours"), ("Encours en retard", "encours_retard"),
    ("Jours de retard (max)", "max_jours_retard"), ("Crédits", "nb_credits"),
]


def _val(ligne: dict, cle):
    # Colonne DÉRIVÉE de l'écran (ex. % P15 = P15 ÷ objectif) : le même rapport que le
    # tableau affiche, pour que le fichier soit le tableau.
    if callable(cle):
        return cle(ligne)
    if isinstance(cle, tuple):
        return (ligne.get(cle[0]) or {}).get(cle[1])
    return ligne.get(cle)


# Une SECTION = (titre, colonnes [(libellé, clé)], lignes [dict]). Un export = 1..n sections.
def _texte(v) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "oui" if v else "non"
    if isinstance(v, float):
        return f"{v:.2f}".replace(".", ",")
    return str(v)


def _csv_sections(sections, entete: list[str]) -> bytes:
    tampon = io.StringIO()
    w = csv.writer(tampon, delimiter=";", lineterminator="\r\n")
    for texte in entete:
        w.writerow([texte])
    for titre, colonnes, lignes in sections:
        w.writerow([])
        if titre:
            w.writerow([titre])
        w.writerow([t for t, _ in colonnes])
        for l in lignes:
            w.writerow([_texte(_val(l, c)) for _, c in colonnes])
    return ("\ufeff" + tampon.getvalue()).encode("utf-8")


def _nom_feuille(titre: str, pris: set) -> str:
    base = "".join(ch for ch in (titre or "Tableau") if ch not in '[]:*?/\\')[:31] or "Tableau"
    nom, k = base, 2
    while nom in pris:
        nom = f"{base[:28]} {k}"
        k += 1
    pris.add(nom)
    return nom


def _xlsx_sections(sections, entete: list[str]) -> bytes:
    wb = Workbook()
    wb.remove(wb.active)
    pris: set = set()
    for titre, colonnes, lignes in sections:
        ws = wb.create_sheet(_nom_feuille(titre or "Tableau de bord", pris))
        for texte in entete:
            ws.append([texte])
        if titre:
            ws.append([titre])
            ws[ws.max_row][0].font = Font(bold=True)
        ws.append([])
        ws.append([t for t, _ in colonnes])
        for cell in ws[ws.max_row]:
            cell.font = Font(bold=True)
        for l in lignes:
            ws.append([_val(l, c) for _, c in colonnes])
        for k, (t, _) in enumerate(colonnes, start=1):
            ws.column_dimensions[ws.cell(row=1, column=k).column_letter].width = \
                max(10, min(40, len(t) + 2))
    tampon = io.BytesIO()
    wb.save(tampon)
    return tampon.getvalue()


def _montant_pdf(v) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "oui" if v else "non"
    if isinstance(v, (int, float)):
        txt = f"{abs(v):,.2f}".replace(",", " ").replace(".", ",")
        if isinstance(v, int):
            txt = txt[:-3]
        return f"-{txt}" if v < 0 else txt
    return str(v)


# PDF : au-delà de COLONNES_PAR_BANDE, un tableau large (DailyTool : ~50 colonnes) serait
# illisible sur une page. Il est découpé en BANDES de colonnes, l'une sous l'autre, et les
# colonnes d'identification (texte : agence, désignation…) sont répétées dans chaque bande —
# comme un classeur Excel imprimé sur plusieurs pages.
COLONNES_PAR_BANDE = 12


def _est_ratio(libelle: str) -> bool:
    """Colonne exprimée en FRACTION par l'API (0,108 = 10,8 %) : montrée en % dans le PDF.
    Le CSV et l'Excel gardent la fraction brute (on calcule dessus)."""
    l = libelle.lower()
    return (l.startswith("%") or l in ("croissance", "par30 (fraction)")
            or l.startswith("couverture") or (l.startswith("taux ") and "usd" not in l))


def _colonnes_cles(colonnes, lignes) -> list[int]:
    """Colonnes d'identification : les premières colonnes TEXTE (au plus 2, parmi les 3 premières)."""
    cles = []
    for k, (_, c) in enumerate(colonnes[:3]):
        valeurs = [_val(l, c) for l in lignes]
        if valeurs and all(v is None or isinstance(v, str) for v in valeurs) and any(valeurs):
            cles.append(k)
        if len(cles) == 2:
            break
    return cles or [0]


def _pdf_sections(sections, entete: list[str]) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    bleu = colors.HexColor("#0B3D5C")
    styles = getSampleStyleSheet()
    cellule = styles["BodyText"].clone("cellule", fontSize=7, leading=8.5)
    droite = cellule.clone("droite", alignment=2)
    tete = cellule.clone("tete", textColor=colors.white)
    tampon = io.BytesIO()
    doc = SimpleDocTemplate(tampon, pagesize=landscape(A4), leftMargin=10 * mm,
                            rightMargin=10 * mm, topMargin=10 * mm, bottomMargin=10 * mm,
                            title=entete[0] if entete else "PopPilot")
    largeur = landscape(A4)[0] - 20 * mm
    histoire = [Paragraph(entete[0], styles["Title"])] if entete else []
    histoire += [Paragraph(t, styles["Normal"]) for t in entete[1:]]

    for titre, colonnes, lignes in sections:
        histoire.append(Spacer(1, 4 * mm))
        if titre:
            histoire.append(Paragraph(titre, styles["Heading3"]))
        valeurs = [[_val(l, c) for _, c in colonnes] for l in lignes]
        numerique = [any(isinstance(v[k], (int, float)) and not isinstance(v[k], bool) for v in valeurs)
                     for k in range(len(colonnes))]
        ratio = [_est_ratio(lib) for lib, _ in colonnes]
        if len(colonnes) <= COLONNES_PAR_BANDE:
            cles, bandes = [], [list(range(len(colonnes)))]
        else:
            cles = _colonnes_cles(colonnes, lignes)
            autres = [k for k in range(len(colonnes)) if k not in cles]
            pas = COLONNES_PAR_BANDE - len(cles)
            bandes = [autres[i:i + pas] for i in range(0, len(autres), pas)]
        for b, bande in enumerate(bandes):
            idx = cles + bande
            donnees = [[Paragraph(f"<b>{colonnes[k][0]}</b>", tete) for k in idx]]
            for v in valeurs:
                donnees.append([Paragraph(
                    (_montant_pdf(v[k] * 100) + " %") if ratio[k] and isinstance(v[k], (int, float))
                    else _montant_pdf(v[k]), droite if numerique[k] else cellule) for k in idx])
            n = len(idx)
            part_cle = 0.16 if cles else 0.0
            larg_cles = [largeur * part_cle] * len(cles)
            reste = largeur - sum(larg_cles)
            if not cles:                                   # tableau étroit : 1re colonne plus large
                premiere = min(0.28, max(1 / n, 0.12)) if n > 1 else 1.0
                larg = [largeur * premiere] + ([largeur * (1 - premiere) / (n - 1)] * (n - 1) if n > 1 else [])
            else:
                larg = larg_cles + [reste / len(bande)] * len(bande)
            t = Table(donnees, repeatRows=1, colWidths=larg)
            style = [("BACKGROUND", (0, 0), (-1, 0), bleu),
                     ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#C9D3DC")),
                     ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                     ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F4F7FA")])]
            if cles:                                       # colonnes répétées : fond distinct
                style.append(("BACKGROUND", (0, 1), (len(cles) - 1, -1), colors.HexColor("#EAF1F6")))
            t.setStyle(TableStyle(style))
            bloc = [t]
            if len(bandes) > 1:
                bloc.insert(0, Paragraph(f"<i>Colonnes {b + 1} / {len(bandes)}</i>", cellule))
            histoire.append(KeepTogether(bloc) if len(lignes) < 25 else bloc[-1])
            histoire.append(Spacer(1, 3 * mm))
    doc.build(histoire)
    return tampon.getvalue()


_TYPES = {"csv": "text/csv; charset=utf-8", "pdf": "application/pdf",
          "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}
_ECRIVAINS = {"csv": _csv_sections, "xlsx": _xlsx_sections, "pdf": _pdf_sections}


MAX_LIGNES_PDF = 3000     # au-delà, un PDF n'est plus lisible (et coûte cher en mémoire)


def _fichier_sections(sections, entete, nom: str, format: str) -> Response:
    n = sum(len(x[2]) for x in sections)
    if format == "pdf" and n > MAX_LIGNES_PDF:
        mille = lambda x: f"{x:,}".replace(",", " ")
        raise HTTPException(413, f"{mille(n)} lignes : trop pour un PDF lisible (maximum {mille(MAX_LIGNES_PDF)}). "
                                 "Télécharger en Excel ou en CSV, ou filtrer (agence, statut…).")
    contenu = _ECRIVAINS[format](sections, entete)
    nom = "".join(ch if (ch.isascii() and ch.isalnum()) or ch in "-_." else "_" for ch in nom) or "PopPilot"
    return Response(content=contenu, media_type=_TYPES[format], headers={
        "Content-Disposition": f"attachment; filename=\"{nom}.{format}\"",
        "Cache-Control": "no-store"})


def _fichier(colonnes, lignes, entete, nom: str, format: str) -> Response:
    return _fichier_sections([(None, colonnes, lignes)], entete, nom, format)


def _format(format: str) -> str:
    if format not in _ECRIVAINS:
        raise HTTPException(422, f"format inconnu : {format} (attendu csv, xlsx ou pdf)")
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
        sexe=q.get("sexe"), groupe=q.get("groupe"), statut=q.get("statut"), user=user)
    # Colonnes sans objet à ce niveau (ex. nom du client au niveau agence) : retirées du fichier.
    colonnes = [c for c in _EPARGNE if c[1] not in _SANS_OBJET_EPARGNE.get(r["niveau"], ())]
    return _fichier(colonnes, r["lignes"], _entete("tableau de bord épargne", r, user),
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


# ─────────────────────────────────────────────────────────────────────────────
# EXPORT GÉNÉRIQUE : tout tableau de l'interface
# ─────────────────────────────────────────────────────────────────────────────
MAX_LIGNES = 100_000


class Colonne(BaseModel):
    libelle: str = Field(max_length=200)
    cle: str = Field(max_length=200)


class Section(BaseModel):
    titre: str | None = Field(None, max_length=300)
    colonnes: list[Colonne] = Field(min_length=1, max_length=200)
    lignes: list[dict]


class DemandeExport(BaseModel):
    titre: str = Field(max_length=300)
    sous_titre: str | None = Field(None, max_length=600)
    nom: str = Field("PopPilot", max_length=150)
    format: str = "csv"
    sections: list[Section] = Field(min_length=1, max_length=30)


@routeur.post("/export/sections")
def export_sections(d: DemandeExport, user: dict = Depends(utilisateur_courant)):
    """Écrit en CSV / Excel / PDF les tableaux que l'écran affiche déjà.

    Les lignes sont celles que l'API a renvoyées à CET utilisateur (cloisonnement déjà
    appliqué) : ce point d'entrée ne lit rien en base et ne calcule rien."""
    format = _format(d.format)
    if sum(len(x.lignes) for x in d.sections) > MAX_LIGNES:
        raise HTTPException(413, f"Export trop volumineux (plus de {MAX_LIGNES:,} lignes).")
    entete = [f"PopPilot — {d.titre}"] + ([d.sous_titre] if d.sous_titre else []) + [
        f"Exporté par {user.get('login') or user.get('email') or '?'} ({user['role']})"]
    sections = [(x.titre, [(c.libelle, c.cle) for c in x.colonnes], x.lignes) for x in d.sections]
    return _fichier_sections(sections, entete, d.nom, format)
