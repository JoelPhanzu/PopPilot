"""
PopPilot API — traitement du grand livre CBS pour SAGE (chantier 5).

  POST /sage/traiter  (multipart : fichier CBS)  → le .xlsx au format SAGE
  GET  /sage/journal                            → derniers traitements (journal_sage_traite)

N'écrit AUCUNE règle comptable : la transformation est celle de engine/traitement_sage.py
(reformatage CG, conversion CDF, colonnes vides, Type_Ecriture = G). Ce routeur ne fait que
lui fournir le TAUX et contrôler le résultat.

RÈGLES CONFIRMÉES PAR LE CDG
- Taux JOURNALIER, lu dans la plateforme (param_taux_change, USD→CDF) à la date comptable
  EXACTE de chaque ligne USD. Un jour sans taux → 422 avec la liste des dates : on ne
  substitue jamais le taux d'un autre jour (un taux voisin donnerait un fichier faux mais
  équilibré, donc indétectable à l'import SAGE).
- N° Pièce, Code journal, N° Section : laissés VIDES, le comptable les renseigne.
- Type_Ecriture = "G" partout. CG : suffixe 0 (USD) / 1 (CDF), complété à 8 chiffres.

CONTRÔLES — le fichier est rendu dans tous les cas (le comptable doit pouvoir l'ouvrir pour
comprendre), mais le statut passe à ALERTE si :
  - Σ Débit CDF ≠ Σ Crédit CDF (écriture non importable en l'état) ;
  - une ligne a un sens autre que « c » / « d » (ni débit ni crédit : montant perdu).
Le statut et les totaux voyagent dans les en-têtes X-Sage-* et dans journal_sage_traite.
"""
from __future__ import annotations

import datetime as dt
import os
import shutil
import tempfile

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from openpyxl.utils.exceptions import InvalidFileException
from sqlalchemy import select

from socle.schema import JournalSageTraite, ParamTauxChange, env_encore_gabarit, get_session
from engine.traitement_sage import ecrire_fichier_sage, traiter_gl_pour_sage

from auth_supabase import ROLES_ACCES_TOTAL, ROLES_ECRITURE, exiger_role, utilisateur_courant
from import_cbs import _ecrire_sur_disque, _nom_sain

routeur = APIRouter(tags=["sage"])

TYPE_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def en_date(v) -> dt.date | None:
    """Date comptable du CBS : cellule date Excel, ou texte JJ/MM/AAAA, AAAA-MM-JJ…"""
    if isinstance(v, dt.datetime):
        return v.date()
    if isinstance(v, dt.date):
        return v
    if v is None:
        return None
    texte = str(v).strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%y", "%Y-%m-%d %H:%M:%S"):
        try:
            return dt.datetime.strptime(texte, fmt).date()
        except ValueError:
            continue
    return None


def _taux_journaliers(session) -> dict[dt.date, float]:
    lignes = session.execute(
        select(ParamTauxChange.date_effet, ParamTauxChange.taux)
        .where(ParamTauxChange.devise_source == "USD", ParamTauxChange.devise_cible == "CDF")
    ).all()
    return {d: t for d, t in lignes}


def traiter(chemin: str, taux: dict[dt.date, float], feuille: str | None = None) -> dict:
    """Moteur + taux du jour + contrôles. Séparé de l'endpoint pour être testé sans HTTP."""
    manquantes: set = set()

    def taux_du_jour(valeur):
        d = en_date(valeur)
        if d is None:
            manquantes.add(f"date illisible : {valeur!r}")
            return 0.0
        if d not in taux:
            manquantes.add(d.isoformat())
            return 0.0
        return taux[d]

    r = traiter_gl_pour_sage(chemin, None, feuille=feuille, taux_du_jour=taux_du_jour)
    if manquantes:
        raise HTTPException(
            422,
            "Taux USD→CDF absent de la plateforme pour : " + ", ".join(sorted(manquantes))
            + ". Le saisir (page Configuration → taux) puis relancer : le traitement "
              "n'utilise jamais le taux d'un autre jour.")

    sans_sens = sum(1 for l in r["lignes"] if l[8] is None and l[9] is None)
    dates = sorted({d for d in (en_date(l[0]) for l in r["lignes"]) if d})
    alertes = []
    if r["ecart_equilibre"]:
        alertes.append(f"Débit ≠ Crédit : écart {r['ecart_equilibre']:,.2f} CDF")
    if sans_sens:
        alertes.append(f"{sans_sens} ligne(s) au sens ni « c » ni « d » (ni débit ni crédit)")
    r.update({
        "sans_sens": sans_sens,
        "periode": f"{dates[0].isoformat()} au {dates[-1].isoformat()}" if dates else None,
        "statut": "ALERTE" if alertes else "OK",
        "alertes": alertes,
    })
    return r


def _journaliser(nom: str, r: dict | None, statut: str, message: str) -> None:
    s = get_session()
    try:
        s.add(JournalSageTraite(
            date_traitement=dt.date.today(), periode=(r or {}).get("periode"),
            fichier_source=nom, lignes_entree=(r or {}).get("nb_lignes"),
            lignes_sortie=(r or {}).get("nb_lignes"), statut=statut, message=message[:500]))
        s.commit()
    finally:
        s.close()


def _ascii(texte: str) -> str:
    """Les en-têtes HTTP sont en latin-1 : on garde le message lisible sans accents."""
    import unicodedata
    return unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode()


@routeur.post("/sage/traiter")
def endpoint_traiter_sage(fichier: UploadFile = File(...),
                          feuille: str | None = Form(None),
                          user: dict = Depends(utilisateur_courant)):
    """Grand livre CBS brut → fichier SAGE (.xlsx), au taux journalier de la plateforme."""
    exiger_role(user, ROLES_ECRITURE)
    gabarit = env_encore_gabarit()
    if gabarit:
        raise HTTPException(503, gabarit)
    nom = _nom_sain(fichier.filename, (".xlsx", ".xlsm"))

    dossier = tempfile.mkdtemp(prefix="sage_")
    try:
        chemin = os.path.join(dossier, nom)
        _ecrire_sur_disque(fichier, chemin)
        s = get_session()
        try:
            taux = _taux_journaliers(s)
        finally:
            s.close()
        try:
            r = traiter(chemin, taux, feuille)
        except HTTPException as e:
            _journaliser(nom, None, "ECHEC", f"par {user['login']} | {e.detail}")
            raise
        except (InvalidFileException, KeyError, IndexError, ValueError, TypeError) as e:
            _journaliser(nom, None, "ECHEC", f"par {user['login']} | {e}")
            raise HTTPException(400, f"Fichier illisible comme grand livre CBS (9 colonnes) : {e}")

        sortie = os.path.join(dossier, "GL_SAGE.xlsx")
        ecrire_fichier_sage(r, sortie)
        with open(sortie, "rb") as f:
            contenu = f.read()
    finally:
        shutil.rmtree(dossier, ignore_errors=True)

    message = (f"par {user['login']} | {r['nb_lignes']} lignes (USD {r['nb_usd']}, CDF {r['nb_cdf']}) | "
               f"D {r['total_debit_cdf']:,.2f} C {r['total_credit_cdf']:,.2f}"
               + (" | " + " ; ".join(r["alertes"]) if r["alertes"] else ""))
    _journaliser(nom, r, r["statut"], message)

    base = os.path.splitext(nom)[0]
    return Response(content=contenu, media_type=TYPE_XLSX, headers={
        "Content-Disposition": f'attachment; filename="{_ascii(base)}_SAGE.xlsx"',
        "X-Sage-Statut": r["statut"],
        "X-Sage-Lignes": str(r["nb_lignes"]),
        "X-Sage-Total-Debit": f"{r['total_debit_cdf']:.2f}",
        "X-Sage-Total-Credit": f"{r['total_credit_cdf']:.2f}",
        "X-Sage-Ecart": f"{r['ecart_equilibre']:.2f}",
        "X-Sage-Periode": _ascii(r["periode"] or ""),
        "X-Sage-Alertes": _ascii(" ; ".join(r["alertes"])),
        "Access-Control-Expose-Headers": "X-Sage-Statut, X-Sage-Lignes, X-Sage-Total-Debit, "
                                         "X-Sage-Total-Credit, X-Sage-Ecart, X-Sage-Periode, "
                                         "X-Sage-Alertes",
    })


@routeur.get("/sage/journal")
def endpoint_journal_sage(limite: int = Query(20, ge=1, le=200),
                          user: dict = Depends(utilisateur_courant)):
    """Derniers traitements SAGE : qui, quoi, quand, avec quel statut."""
    exiger_role(user, ROLES_ACCES_TOTAL)
    s = get_session()
    try:
        lignes = s.execute(select(JournalSageTraite).order_by(JournalSageTraite.id.desc())
                           .limit(limite)).scalars().all()
        return {"traitements": [
            {"date": l.date_traitement.isoformat(), "periode": l.periode,
             "fichier": l.fichier_source, "lignes": l.lignes_sortie,
             "statut": l.statut, "message": l.message} for l in lignes]}
    finally:
        s.close()
