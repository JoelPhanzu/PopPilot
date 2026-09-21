"""
PopPilot — export Excel des tableaux de bord.

PRINCIPE : ce qui est exporté est EXACTEMENT ce qui est affiché. Les exports
appellent les mêmes moteurs que les écrans, avec le même arrêté et le même
cloisonnement — il n'y a pas de « requête d'export » qui irait chercher les
données autrement. Un classeur qui ne dirait pas la même chose que l'écran dont
il sort serait pire qu'utile : c'est lui qui circule en réunion.

TRAÇABILITÉ : chaque feuille commence par un bandeau qui dit ce qu'on regarde —
domaine, arrêté, périmètre, source, horodatage, et qui l'a produit. Un classeur
détaché de son écran doit pouvoir être daté et attribué sans témoin ; sans ce
bandeau, deux exports du même domaine à deux arrêtés sont indiscernables une
fois renommés.

DEVISE : les montants sortent en USD, source de vérité (§43), sauf mention
contraire portée par le bandeau. Rien n'est converti ici.
"""
from __future__ import annotations

import datetime as dt
import io

from fastapi import APIRouter, Depends, HTTPException, Response
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from auth_supabase import (ROLES_ACCES_TOTAL, exiger_role, filtrer_par_agence,
                           utilisateur_courant)
from engine.derivation import deriver_provisions
from engine.epargne import nb_epargnants, synthese_epargne
from engine.etats_detail import etats_detailles
from engine.indicateurs import indicateurs_prudentiels
from engine.par import calculer_par
from engine.budget import suivi_budgetaire

routeur = APIRouter(tags=["export"])

TYPE_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

# Charte MICROPOP : bleu principal en en-tête, texte blanc.
BLEU = PatternFill("solid", fgColor="0B3D5C")
FOND = PatternFill("solid", fgColor="F4F7FA")
BLANC_GRAS = Font(bold=True, color="FFFFFF")
GRAS = Font(bold=True)
GRIS = Font(color="58595B", size=9)

MONTANT = "#,##0.00"
ENTIER = "#,##0"
TAUX = "0.00"


def _date(valeur: str) -> dt.date:
    try:
        return dt.date.fromisoformat(valeur)
    except (ValueError, TypeError):
        raise HTTPException(400, f"Date invalide : {valeur} (format attendu AAAA-MM-JJ)")


def _bandeau(ws, titre: str, arrete: dt.date, portee: str, source: str, user: dict) -> int:
    """Écrit l'en-tête de traçabilité. Renvoie la première ligne libre."""
    ws["A1"] = titre
    ws["A1"].font = Font(bold=True, size=13, color="0B3D5C")
    ws["A2"] = (f"Arrêté du {arrete.strftime('%d/%m/%Y')} · {portee} · "
                f"produit le {dt.datetime.now().strftime('%d/%m/%Y à %H:%M')} "
                f"par {user.get('login') or user.get('role')}")
    ws["A2"].font = GRIS
    ws["A3"] = f"Source : {source}. Montants en USD sauf mention contraire."
    ws["A3"].font = GRIS
    return 5


def _entete(ws, ligne: int, colonnes: list[str]) -> int:
    for i, libelle in enumerate(colonnes, start=1):
        c = ws.cell(row=ligne, column=i, value=libelle)
        c.fill = BLEU
        c.font = BLANC_GRAS
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws.freeze_panes = ws.cell(row=ligne + 1, column=1)
    return ligne + 1


def _largeurs(ws, largeurs: list[int]) -> None:
    for i, l in enumerate(largeurs, start=1):
        ws.column_dimensions[get_column_letter(i)].width = l


def _ligne(ws, num: int, valeurs: list, formats: list[str | None] | None = None,
           gras: bool = False, fond: bool = False) -> int:
    for i, v in enumerate(valeurs, start=1):
        c = ws.cell(row=num, column=i, value=v)
        if formats and i <= len(formats) and formats[i - 1]:
            c.number_format = formats[i - 1]
        if gras:
            c.font = GRAS
        if fond:
            c.fill = FOND
    return num + 1


def _reponse(wb: Workbook, nom: str) -> Response:
    """Sérialise le classeur et l'envoie en téléchargement."""
    tampon = io.BytesIO()
    wb.save(tampon)
    #  `filename*` (RFC 5987) porte les accents ; `filename` reste en repli ASCII
    #  pour les clients qui l'ignorent. Sans les deux, le nom arrive mutilé.
    ascii_sur = nom.encode("ascii", "ignore").decode() or "export.xlsx"
    return Response(
        content=tampon.getvalue(),
        media_type=TYPE_XLSX,
        headers={
            "Content-Disposition":
                f"attachment; filename=\"{ascii_sur}\"; "
                f"filename*=UTF-8''{nom.replace(' ', '%20')}",
        },
    )


def _portee(user: dict) -> str:
    if user["role"] in ROLES_ACCES_TOTAL:
        return "MICROPOP, toutes agences"
    return f"Agence {user.get('agence') or '—'}"


# ─────────────────────────────────────────────────────────────────────────────
# CRÉDIT — cloisonné par agence, comme l'écran
# ─────────────────────────────────────────────────────────────────────────────
@routeur.get("/export/credit")
def export_credit(arrete: str, user: dict = Depends(utilisateur_courant)):
    d = _date(arrete)
    r = calculer_par(d)
    agences = [{"agence": a.designation, "encours": a.encours, "par1": a.par1,
                "par30": a.par30, "pct_par30": a.pct_par30} for a in r["agences"]]
    agences = filtrer_par_agence(user, agences)
    total = user["role"] in ROLES_ACCES_TOTAL

    wb = Workbook()
    ws = wb.active
    ws.title = "PAR par agence"
    n = _bandeau(ws, "Crédit — portefeuille à risque", d, _portee(user),
                 "moteur engine/par.py (validé écart nul)", user)
    n = _entete(ws, n, ["Agence", "Encours", "PAR 1", "PAR 30", "PAR 30 (%)"])
    for a in sorted(agences, key=lambda x: -(x["encours"] or 0)):
        n = _ligne(ws, n, [a["agence"], a["encours"], a["par1"], a["par30"], a["pct_par30"]],
                   [None, MONTANT, MONTANT, MONTANT, TAUX])
    #  Le total est la somme des lignes EXPORTÉES : pour un rôle AGENCE, jamais
    #  l'agrégat institution (même règle que l'écran).
    somme = lambda cle: sum(a[cle] or 0 for a in agences)   # noqa: E731
    n = _ligne(ws, n, ["TOTAL " + ("MICROPOP" if total else (user.get("agence") or "")),
                       somme("encours"), somme("par1"), somme("par30"),
                       (somme("par30") / somme("encours") * 100) if somme("encours") else None],
               [None, MONTANT, MONTANT, MONTANT, TAUX], gras=True, fond=True)
    _largeurs(ws, [34, 18, 16, 16, 13])

    if total:
        g = r["global"]
        ws2 = wb.create_sheet("Synthèse")
        m = _bandeau(ws2, "Crédit — synthèse institution", d, _portee(user),
                     "moteurs engine/par.py et engine/derivation.py", user)
        m = _entete(ws2, m, ["Indicateur", "Montant", "% de l'encours"])
        for libelle, valeur, pct in (
            ("Encours de crédit", g.encours, None),
            ("PAR 1 — risque global (≥ 1 jour)", g.par1, g.pct_par1),
            ("PAR 30 — norme réglementaire (≥ 31 jours)", g.par30, g.pct_par30),
            ("PAR 90 — risque installé (≥ 91 jours)", g.par90, g.pct_par90),
        ):
            m = _ligne(ws2, m, [libelle, valeur, pct], [None, MONTANT, TAUX])
        m = _ligne(ws2, m, ["Nombre de crédits", g.nb_credits, None], [None, ENTIER, None])
        m = _ligne(ws2, m, ["Nombre d'emprunteurs", g.nb_clients, None], [None, ENTIER, None])

        try:
            prov = deriver_provisions(d)
            m = _ligne(ws2, m, [], [])
            m = _ligne(ws2, m, ["Provisions (barème + compléments manuels DAF)",
                                prov.get("provision_capital_totale"), None],
                       [None, MONTANT, None], gras=True)
            for agence, montant in sorted((prov.get("par_agence") or {}).items()):
                m = _ligne(ws2, m, [f"    {agence}", montant, None], [None, MONTANT, None])
        except Exception as e:                                   # noqa: BLE001
            #  Les provisions peuvent manquer sans que le PAR manque : on le DIT
            #  dans le classeur plutôt que de livrer une feuille tronquée.
            _ligne(ws2, m, [f"Provisions indisponibles : {e}"], [None])
        _largeurs(ws2, [46, 20, 16])

    return _reponse(wb, f"PopPilot_credit_{d.isoformat()}.xlsx")


# ─────────────────────────────────────────────────────────────────────────────
# COMPTABILITÉ — le référentiel BCC en entier, comptes compris
# ─────────────────────────────────────────────────────────────────────────────
@routeur.get("/export/comptabilite")
def export_comptabilite(arrete: str, user: dict = Depends(utilisateur_courant)):
    exiger_role(user, ROLES_ACCES_TOTAL)
    d = _date(arrete)
    detail = etats_detailles(d)

    wb = Workbook()
    wb.remove(wb.active)

    for cle, titre in (("actif", "Bilan ACTIF"), ("passif", "Bilan PASSIF"),
                       ("resultat", "Compte de résultat")):
        ws = wb.create_sheet(titre[:31])
        n = _bandeau(ws, f"{titre} — référentiel BCC intégral", d, _portee(user),
                     "moteur engine/etats_detail.py (écart nul contre l'agrégat validé)", user)
        n = _entete(ws, n, ["Code", "Libellé", "Montant", "Sens dans le sous-total"])
        for l in detail[cle]:
            est_total = l["nature"] != "ligne"
            n = _ligne(ws, n,
                       [l["code"], l["libelle"], l["montant"],
                        "" if est_total else ("déduit" if l["signe"] < 0 else "ajouté")],
                       [None, None, MONTANT, None],
                       gras=est_total, fond=est_total)
        _largeurs(ws, [14, 72, 20, 22])

    #  Le détail compte par compte, avec la ligne du référentiel à laquelle il
    #  est rattaché : c'est ce qui permet de justifier un montant sans ressortir
    #  la balance.
    ws = wb.create_sheet("Comptes")
    n = _bandeau(ws, "Comptes de balance et leur rattachement", d, _portee(user),
                 "balance importée + référentiel BCC", user)
    n = _entete(ws, n, ["État", "Code ligne", "Ligne du référentiel", "Compte",
                        "Libellé du compte", "Solde net"])
    for cle, etat in (("Actif", detail["actif"]), ("Passif", detail["passif"]),
                      ("Résultat", detail["resultat"])):
        for l in etat:
            for c in l["comptes"]:
                n = _ligne(ws, n, [cle, l["code"], l["libelle"], c["numero_compte"],
                                   c["libelle"], c["solde_net"]],
                           [None, None, None, None, None, MONTANT])
    _largeurs(ws, [11, 14, 60, 18, 46, 18])

    #  Contrôles : un classeur qui circule doit porter ses propres réserves.
    ws = wb.create_sheet("Contrôles")
    c = detail["controles"]
    n = _bandeau(ws, "Contrôles des états financiers", d, _portee(user),
                 "engine/etats_detail.py", user)
    n = _entete(ws, n, ["Contrôle", "Valeur"])
    for libelle, valeur, fmt in (
        ("Bilan équilibré (actif − passif)", c["bilan_equilibre_ecart"], MONTANT),
        ("Bilan équilibré ?", "oui" if c["equilibre"] else "NON", None),
        ("Écart avec l'agrégat validé (doit être nul)", c["ecart_avec_agregat"], MONTANT),
        ("Écart sur le résultat", c["ecart_resultat_avec_agregat"], MONTANT),
        ("Comptes de balance lus", c["nb_comptes_balance"], ENTIER),
        ("Comptes non placés dans le référentiel", c["nb_comptes_non_places"], ENTIER),
        ("Résultat porté au passif", detail["resultat_source"], None),
    ):
        n = _ligne(ws, n, [libelle, valeur], [None, fmt])
    if c["comptes_non_places"]:
        n = _ligne(ws, n, [])
        n = _ligne(ws, n, ["Comptes non placés :"], gras=True)
        for compte in c["comptes_non_places"]:
            n = _ligne(ws, n, ["", compte])
    _largeurs(ws, [48, 28])

    #  Indicateurs prudentiels : ils peuvent manquer alors que le bilan sort.
    try:
        ind = indicateurs_prudentiels(d)
        ws = wb.create_sheet("Indicateurs")
        n = _bandeau(ws, "Indicateurs prudentiels BCC", d, _portee(user),
                     "moteur engine/indicateurs.py", user)
        n = _entete(ws, n, ["Code", "Valeur", "Norme", "Numérateur", "Dénominateur",
                            "Motif si non calculé", "Source"])
        for code, i in ind["indicateurs"].items():
            n = _ligne(ws, n, [code, i.get("valeur"), i.get("norme"), i.get("num"),
                               i.get("den"), i.get("motif", ""), i.get("source", "")],
                       [None, TAUX, None, MONTANT, MONTANT, None, None])
        n = _ligne(ws, n, [])
        n = _ligne(ws, n, ["Agrégats de calcul"], gras=True)
        n = _entete(ws, n, ["Agrégat", "Valeur"])
        for nom, valeur in ind["agregats"].items():
            n = _ligne(ws, n, [nom, valeur], [None, MONTANT])
        if ind.get("avertissements"):
            n = _ligne(ws, n, [])
            n = _ligne(ws, n, ["Réserves publiées par le moteur"], gras=True)
            for cle_a, message in ind["avertissements"].items():
                n = _ligne(ws, n, [cle_a, message])
        _largeurs(ws, [32, 16, 14, 20, 20, 60, 34])
    except Exception as e:                                       # noqa: BLE001
        ws = wb.create_sheet("Indicateurs")
        _ligne(ws, 1, [f"Indicateurs indisponibles pour cet arrêté : {e}"])
        _largeurs(ws, [110])

    return _reponse(wb, f"PopPilot_comptabilite_{d.isoformat()}.xlsx")


# ─────────────────────────────────────────────────────────────────────────────
# ÉPARGNE
# ─────────────────────────────────────────────────────────────────────────────
@routeur.get("/export/epargne")
def export_epargne(arrete: str, user: dict = Depends(utilisateur_courant)):
    exiger_role(user, ROLES_ACCES_TOTAL)
    d = _date(arrete)
    e = synthese_epargne(d)
    e["nb_epargnants"] = nb_epargnants(d)

    wb = Workbook()
    ws = wb.active
    ws.title = "Synthèse"
    n = _bandeau(ws, "Épargne — synthèse", d, _portee(user),
                 "moteur engine/epargne.py (inventaire dépôt)", user)
    n = _entete(ws, n, ["Indicateur", "Valeur"])
    for libelle, valeur, fmt in (
        ("Encours total (converti USD)", e["encours_total"], MONTANT),
        ("Dépôts à vue", e["depots_a_vue"], MONTANT),
        ("Dépôts à terme", e["depots_a_terme"], MONTANT),
        ("Épargne obligatoire", e["depots_obligatoire"], MONTANT),
        ("Épargne des groupes", e["epargne_groupe"], MONTANT),
        ("Nombre de comptes", e["nb_comptes"], ENTIER),
        ("Nombre d'épargnants", e["nb_epargnants"], ENTIER),
        ("Taux de conversion appliqué (CDF/USD)", e["taux_change"], MONTANT),
    ):
        n = _ligne(ws, n, [libelle, valeur], [None, fmt])
    _largeurs(ws, [40, 22])

    ws2 = wb.create_sheet("Par devise d'origine")
    m = _bandeau(ws2, "Épargne par type et par devise D'ORIGINE", d, _portee(user),
                 "inventaire dépôt — montants NON convertis", user)
    #  Les montants par devise ne s'additionnent PAS entre eux (facteur ~2268).
    #  La contre-valeur USD, elle, se totalise : c'est sa raison d'être, et c'est
    #  le seul total général de cette feuille. Même règle qu'à l'écran.
    taux = e["taux_change"]

    def _en_usd(montant_origine, devise):
        """Seul le CDF est converti, au taux de l'arrêté — comme `to_usd` du moteur.
        Une devise inconnue n'est pas convertie à l'aveugle : la case reste vide."""
        if devise == "USD":
            return montant_origine
        if devise == "CDF":
            return (montant_origine / taux) if taux else None
        return None

    m = _ligne(ws2, m, ["Montants dans leur devise d'émission : ils ne s'additionnent pas "
                        "entre eux. Seule la contre-valeur USD se totalise."], gras=True)
    m += 1
    entete_usd = ("Contre-valeur USD" if taux
                  else "Contre-valeur USD (aucun taux saisi pour cet arrêté)")
    m = _entete(ws2, m, ["Type de dépôt", "Devise", "Montant (devise d'origine)", entete_usd])
    for cle, montant_origine in sorted(e["par_type_devise"].items()):
        type_depot, _, devise = cle.rpartition("/")
        m = _ligne(ws2, m, [type_depot, devise, montant_origine,
                            _en_usd(montant_origine, devise)],
                   [None, None, MONTANT, MONTANT])

    m = _ligne(ws2, m, [])
    m = _entete(ws2, m, ["Total par devise", "Devise", "Montant", "Contre-valeur USD"])
    total_usd = 0.0
    convertible = True
    for devise, montant_origine in sorted(e["par_devise_origine"].items()):
        valeur = _en_usd(montant_origine, devise)
        if valeur is None:
            convertible = False
        else:
            total_usd += valeur
        m = _ligne(ws2, m, ["Total", devise, montant_origine, valeur],
                   [None, None, MONTANT, MONTANT], gras=True)

    m = _ligne(ws2, m, ["TOTAL CONVERTI EN USD", "", "",
                        total_usd if convertible else None],
               [None, None, None, MONTANT], gras=True, fond=True)
    #  Deux chemins pour le même nombre : la somme des contre-valeurs doit
    #  retomber sur l'encours total du moteur. On le publie plutôt que de le supposer.
    if convertible:
        m = _ligne(ws2, m, ["Contrôle — écart avec l'encours du moteur",
                            "", "", total_usd - e["encours_total"]],
                   [None, None, None, MONTANT])
    _largeurs(ws2, [28, 12, 26, 24])

    return _reponse(wb, f"PopPilot_epargne_{d.isoformat()}.xlsx")


# ─────────────────────────────────────────────────────────────────────────────
# BUDGET — une feuille par volet, les TROIS lectures côte à côte
# ─────────────────────────────────────────────────────────────────────────────
@routeur.get("/export/budget")
def export_budget(arrete: str, precedent: str | None = None, hypothese: str = "H1",
                  user: dict = Depends(utilisateur_courant)):
    exiger_role(user, ROLES_ACCES_TOTAL)
    d = _date(arrete)
    r = suivi_budgetaire(d, precedent=_date(precedent) if precedent else None,
                         hypothese=hypothese)

    wb = Workbook()
    wb.remove(wb.active)

    #  À l'écran les trois lectures sont des onglets, pour ne pas aligner douze
    #  colonnes de nombres. Dans un classeur la largeur n'est pas un problème :
    #  on les met côte à côte, c'est là qu'on les compare.
    colonnes = ["Ligne budgétaire",
                "Budget du mois", "Réalisé du mois", "Écart mois", "% réalisation",
                "Budget annuel", "Réalisé cumulé", "Écart annuel", "% progression",
                "Budget cumulé à date", "Écart à date", "% réalisation à date"]
    formats = [None] + [MONTANT, MONTANT, MONTANT, TAUX] * 2 + [MONTANT, MONTANT, TAUX]

    groupes = {"charge": "Charges", "produit": "Produits"}
    for sens, titre in groupes.items():
        lignes = [l for l in r["lignes"] if l["sens"] == sens]
        ws = wb.create_sheet(titre)
        n = _bandeau(ws, f"Suivi budgétaire — {titre.lower()}", d,
                     f"exercice {r['exercice']}, mois {r['mois']:02d}, hypothèse {r['hypothese']}",
                     "moteur engine/budget.py — balance sans retraitement", user)
        if not r["mapping_present"]:
            n = _ligne(ws, n, [r["motif_realise_absent"]], gras=True)
            n += 1
        if not r["niveau_mensuel_disponible"] and r.get("motif_mensuel_absent"):
            n = _ligne(ws, n, [r["motif_mensuel_absent"]], gras=True)
            n += 1
        n = _entete(ws, n, colonnes)

        for l in sorted(lignes, key=lambda x: -abs(x["realise_cumule"] or 0)):
            #  Ligne non budgétée : « - » en budget, écart et taux ; seul le
            #  réalisé est retenu. Un « 0,00 » se lirait « budgété à zéro », et
            #  l'écart vaudrait le réalisé entier, présenté comme un dépassement.
            def avec_realise(budget, realise, ecart, pct):
                """Budget, réalisé, écart, taux — 4 cellules."""
                if not budget:
                    return ["-", realise, "-", "-"]
                return [budget, realise, ecart, (pct * 100) if pct is not None else None]

            def sans_realise(budget, ecart, pct):
                """Budget, écart, taux — 3 cellules : le réalisé cumulé est déjà
                en colonne « Réalisé cumulé », le répéter n'apprendrait rien."""
                if not budget:
                    return ["-", "-", "-"]
                return [budget, ecart, (pct * 100) if pct is not None else None]

            n = _ligne(ws, n, [l["ligne"],
                               *avec_realise(l["budget_mois"], l["realise_mois"],
                                             l["ecart_mois"], l["pct_realisation"]),
                               *avec_realise(l["budget_annuel"], l["realise_cumule"],
                                             l["ecart_annuel"], l["pct_progression"]),
                               *sans_realise(l["budget_cumule_a_date"], l["ecart_a_date"],
                                             l["pct_realisation_a_date"])],
                       formats)

        def total(champ):
            return sum(l[champ] or 0 for l in lignes)

        n = _ligne(ws, n, [f"TOTAL {titre.lower()}",
                           total("budget_mois"), total("realise_mois"), total("ecart_mois"), None,
                           total("budget_annuel"), total("realise_cumule"),
                           total("ecart_annuel"), None,
                           total("budget_cumule_a_date"), total("ecart_a_date"), None],
                   formats, gras=True, fond=True)
        _largeurs(ws, [46] + [17, 17, 15, 13] * 2 + [19, 15, 13])

    #  Les lignes qu'aucun volet ne réclame (sens absent du mapping) ne sont dans
    #  aucun total : elles sortent à part, pour être corrigées.
    orphelines = [l for l in r["lignes"] if l["sens"] not in groupes]
    if orphelines:
        ws = wb.create_sheet("Sans sens renseigné")
        n = _bandeau(ws, "Lignes sans sens renseigné dans le mapping", d, _portee(user),
                     "mapping_budget — à compléter", user)
        n = _ligne(ws, n, ["Ces lignes ne sont ni charge ni produit : elles n'entrent "
                           "dans aucun volet, donc dans aucun total."], gras=True)
        n += 1
        n = _entete(ws, n, ["Ligne budgétaire", "Budget annuel", "Réalisé cumulé"])
        for l in orphelines:
            n = _ligne(ws, n, [l["ligne"], l["budget_annuel"], l["realise_cumule"]],
                       [None, MONTANT, MONTANT])
        _largeurs(ws, [52, 20, 20])

    return _reponse(wb, f"PopPilot_budget_{d.isoformat()}.xlsx")
