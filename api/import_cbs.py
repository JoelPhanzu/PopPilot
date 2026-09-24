"""
PopPilot API — IMPORT des fichiers du CBS depuis le web (endpoint POST /import/{domaine}).

Le socle est vide tant que personne n'a chargé d'extraction : tous les écrans affichent
« aucune donnée pour cet arrêté ». Jusqu'ici l'import ne se faisait qu'en ligne de commande,
sur la machine qui porte les fichiers. Cet endpoint EXPOSE les mêmes fonctions d'ingestion,
sans en réécrire une ligne : `ingest/` reste la seule autorité sur la lecture des fichiers.

CE QU'IL NE FAIT PAS
  - Aucun calcul, aucune transformation : le fichier est écrit sur disque, puis confié tel
    quel à `ingest.importer_*`. Ce qui est validé au centime en local l'est donc aussi ici.
  - Aucune écriture hors des tables de faits : l'idempotence (purge du snapshot de la
    date_arrete) reste celle de `socle/historisation.py`, règle I-4.

GARDE-FOUS PROPRES À L'EXPOSITION SUR LE WEB
  1. Rôles : réservé à DIRECTION / CDG (`ROLES_ECRITURE`). L'AUDIT lit tout mais n'écrit
     rien — « accès total » en lecture ne donne pas le droit d'importer.
  2. Nom de fichier assaini : un nom venu du navigateur ne doit jamais décider d'un chemin
     sur le serveur (« ../../ »). On garde un nom lisible, car il part dans import_log.
  3. Taille plafonnée, écriture par morceaux : l'inventaire épargne fait ~170 000 lignes ;
     on ne charge pas un tel fichier en mémoire, et on refuse au-delà du plafond.
  4. Paramètre inattendu = refus, jamais un silence : `devise=CDF` envoyé au domaine crédit
     serait ignoré sans bruit, et l'opérateur croirait avoir chargé du CDF.
  5. Un fichier illisible répond 400 (le fichier est en cause), jamais 404 ni 500.
  6. `api/.env` resté au gabarit → 503 : mieux vaut refuser que d'importer dans une base
     SQLite locale pendant que l'opérateur croit alimenter Supabase.

L'endpoint est volontairement SYNCHRONE (`def`, pas `async def`) : les imports sont
bloquants (~15 s pour l'épargne). FastAPI exécute alors la fonction dans son pool de
threads au lieu de figer la boucle d'événements — sinon toute l'API reste muette
pendant l'import.
"""
from __future__ import annotations

import datetime as dt
import os
import re
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from typing import Callable

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic.fields import FieldInfo
from openpyxl.utils.exceptions import InvalidFileException
from sqlalchemy import select

from socle.schema import ImportLog, cible_base, env_encore_gabarit, get_session

from ingest.import_balance import importer_balance
from ingest.import_budget import importer_budget
from ingest.import_credit import importer_credit
from ingest.import_epargne import importer_epargne
from ingest.import_budget import importer_mapping_budget
from ingest.import_objectifs import importer_objectifs
from ingest.import_compte_resultat_agence import importer_compte_resultat_agence
from ingest.import_taux import importer_taux
from ingest.import_remboursements import importer_remboursements

from auth_supabase import (ROLES_ACCES_TOTAL, ROLES_ECRITURE, exiger_role,
                           utilisateur_courant)

routeur = APIRouter(tags=["import"])

# Plafond de taille. L'inventaire dépôt complet (~170 000 comptes) pèse quelques dizaines
# de Mo ; 200 Mo laisse de la marge sans ouvrir la porte à un envoi qui remplirait le disque.
TAILLE_MAX_MO = int(os.environ.get("POPPILOT_IMPORT_MAX_MO", "200"))

TABLEUR = (".xlsx", ".xlsm", ".xls")


@dataclass(frozen=True)
class Domaine:
    """Ce qu'il faut savoir pour confier un fichier à la bonne fonction d'ingestion."""
    libelle: str
    fonction: Callable[..., dict]
    extensions: tuple[str, ...]
    requis: tuple[str, ...]
    optionnels: tuple[str, ...]
    # L'ingestion écrit-elle elle-même dans import_log ? (objectifs et budget : non)
    journalise: bool
    aide: str


DOMAINES: dict[str, Domaine] = {
    "credit": Domaine(
        libelle="Extraction crédit (SIG, colonnes A→AF)",
        fonction=importer_credit, extensions=TABLEUR,
        requis=("date_arrete",), optionnels=("feuille",), journalise=True,
        aide="Extraction mensuelle des prêts actifs. date_arrete = date comptable "
             "(un import du 4 mai portant l'arrêté du 30 avril se range en avril).",
    ),
    "balance": Domaine(
        libelle="Balance comptable (export SAGE)",
        fonction=importer_balance, extensions=TABLEUR,
        requis=("date_arrete",), optionnels=("feuille", "devise"), journalise=True,
        aide="Balance brute ; le solde net est recalculé (Débit − Crédit) s'il manque. "
             "La balance USD et la balance CDF d'un même arrêté cohabitent : préciser la devise.",
    ),
    "epargne": Domaine(
        libelle="Inventaire dépôt / épargne",
        fonction=importer_epargne, extensions=(".csv",) + TABLEUR,
        requis=("date_arrete",), optionnels=(), journalise=True,
        aide="Inventaire des comptes de dépôt (CSV ou xlsx). Lu par en-têtes : "
             "id_cpte, devise, solde_fin, montant_depot…",
    ),
    "objectifs": Domaine(
        libelle="Roster + objectifs des agents (fichier OBJECTIF)",
        fonction=importer_objectifs, extensions=TABLEUR,
        requis=("date_effet",), optionnels=(), journalise=False,
        aide="Double source : liste des agents (détection des orphelins) et leurs objectifs. "
             "Versionné à date d'effet : le roster de mai ne vaut que pour mai (date d'effet = "
             "1er du mois). Feuille « OBJECTIF », ligne 1 = en-têtes, une ligne par agent : "
             "A Agence | B Superviseur | C Agent de crédit | D Nombre à décaisser | E Volume | "
             "F Portefeuille (encours) | G Portefeuille (nb clients) | H PAR (0,05 = 5 %). "
             "Noms d'agence, de superviseur et d'agent ÉCRITS EXACTEMENT comme dans "
             "l'extraction crédit du CBS — sinon l'agent passe en orphelin.",
    ),
    "budget_mapping": Domaine(
        libelle="Mapping budgétaire (fichier de SUIVI budgétaire, 2 feuilles)",
        fonction=importer_mapping_budget, extensions=TABLEUR,
        requis=(), optionnels=("date_effet", "feuille_charges", "feuille_produits"),
        journalise=False,
        aide="Classeur à DEUX feuilles, une par sens : un nom contenant « résultat » et "
             "« charge », un autre contenant « résultat » et « produit » (casse, accents, "
             "singulier/pluriel et mots en plus sans importance — « Résultat Produit » "
             "convient). Dans chaque feuille : ligne 1 = en-têtes, colonne A = numéro de "
             "compte comptable, colonne C = libellé de la ligne budgétaire (colonne B "
             "libre). SANS ce mapping, le réalisé du suivi budgétaire vaut 0,00 sur "
             "toutes les lignes.",
    ),
    "compte_resultat_agence": Domaine(
        libelle="Compte de résultat par agence (fichier isolé du CDG)",
        fonction=importer_compte_resultat_agence, extensions=(".xlsx", ".xlsm"),
        requis=("date_arrete",), optionnels=("feuille",), journalise=True,
        aide="Fichier mensuel COMPTE_RESULTAT_<mois>_isolé.xlsx, feuille Feuil2 : colonne A = "
             "poste, B..G = Victoire, Ozone, Goma, Lubumbashi, Masina, Gombe, H = MICROPOP. "
             "Refusé si la colonne MICROPOP ne redonne pas la somme des 6 agences.",
    ),
    "remboursements": Domaine(
        libelle="Crédits remboursés (intérêts encaissés du mois)",
        fonction=importer_remboursements, extensions=(".xlsx", ".xlsm"),
        requis=("date_arrete",), optionnels=("feuille",), journalise=True,
        aide="Fichier CBS « Crédits remboursés » (9 colonnes, n° de dossier en E). Chaque "
             "remboursement est rattaché à son agent / superviseur / agence par le n° de "
             "dossier : encours du mois, sinon du mois précédent (crédit soldé dans le mois). "
             "Importer d'abord l'encours crédit du même arrêté. Sert la productivité, pas les primes.",
    ),
    "taux_change": Domaine(
        libelle="Taux de change USD→CDF (fichier Date | Taux)",
        fonction=importer_taux, extensions=(".xlsx", ".xlsm"),
        requis=(), optionnels=("remplacer",), journalise=False,
        aide="Deux colonnes : Date et Taux (un taux par jour). Les dates nouvelles sont "
             "ajoutées, les identiques ignorées. Une date déjà en base avec un AUTRE taux "
             "bloque l'import (elle sert au FINA, à l'AML) : écrire « oui » dans Remplacer "
             "pour l'écraser sciemment.",
    ),
    "budget": Domaine(
        libelle="Budget annuel (charges et produits consolidés)",
        fonction=importer_budget, extensions=TABLEUR,
        requis=("exercice",), optionnels=("hypothese", "feuille"), journalise=False,
        aide="Budget mois par mois (non linéaire). Remplace le budget de l'exercice "
             "et de l'hypothèse indiqués.",
    ),
}

# Nom de fichier : on garde ce qui reste lisible dans le journal, on neutralise le reste.
# Les séparateurs de chemin ne sont PAS dans cette liste : un nom ne peut donc pas
# désigner un autre dossier que celui qu'on a créé pour lui.
_CARACTERES_SAINS = re.compile(r"[^A-Za-z0-9._ ()+-]")

# Erreurs qui disent « ce fichier n'est pas celui qu'on attendait » : elles valent 400
# (l'appelant corrige en renvoyant le bon fichier), pas 500 (panne du serveur).
#   - ValueError            : contrôle d'en-tête des modules d'ingestion (règle I-2).
#   - BadZipFile            : .xlsx corrompu, ou fichier qui n'en est pas un.
#   - InvalidFileException  : VRAI .xls (BIFF), qu'openpyxl ne sait pas lire. Le cas se
#     produit pour de bon : l'extraction crédit arrive en « .xls » qui est en réalité du
#     xlsx, et le jour où le CBS en exporte un authentique, l'opérateur doit lire pourquoi.
# Rien d'autre : une exception inattendue est un défaut de la plateforme, et un 500 le dit
# honnêtement — la déguiser en « fichier refusé » enverrait chercher l'erreur dans le fichier.
ERREURS_DE_FICHIER = (ValueError, zipfile.BadZipFile, InvalidFileException)


def _date(valeur: str, nom: str) -> dt.date:
    try:
        return dt.date.fromisoformat(valeur.strip())
    except ValueError:
        raise HTTPException(422, f"{nom} invalide : {valeur!r} (format attendu AAAA-MM-JJ).")


def _nom_sain(nom: str | None, extensions: tuple[str, ...]) -> str:
    """Nom de fichier sûr ET lisible (il est conservé dans import_log, règle I-9)."""
    base = os.path.basename((nom or "").replace("\\", "/")).strip()
    base = _CARACTERES_SAINS.sub("_", base).lstrip(". ")
    tige, extension = os.path.splitext(base)
    if not tige:
        raise HTTPException(400, "Fichier sans nom exploitable.")
    extension = extension.lower()
    if extension not in extensions:
        raise HTTPException(
            400,
            f"Extension {extension or '(aucune)'} inattendue pour ce domaine : "
            f"attendu {', '.join(extensions)}.")
    return tige[:100] + extension


def _est_marqueur_fastapi(valeur) -> bool:
    """La valeur est-elle le DÉFAUT `Form(None)` de la signature, et non une saisie ?

    Appelé par HTTP, FastAPI résout chaque `Form(None)` en `None`. Appelé
    DIRECTEMENT — ce que font les suites de tests du dépôt —, le défaut reste
    l'objet `FieldInfo` lui-même : ni None, ni une chaîne. Sans ce filtre, tout
    champ ajouté à la signature se met à ressembler à un paramètre fourni, et
    l'endpoint refuse en 422 « le domaine n'accepte pas … » un appel qui ne lui
    a pourtant rien envoyé. Le défaut est silencieux pour les appels HTTP et
    n'apparaît qu'aux tests, d'où sa neutralisation ici, une fois pour toutes.
    """
    return isinstance(valeur, FieldInfo)


def _parametres(domaine: str, spec: Domaine, fournis: dict) -> dict:
    """Traduit les champs du formulaire en arguments de la fonction d'ingestion.

    Un paramètre absent des `requis`/`optionnels` du domaine est REFUSÉ. L'ignorer
    en silence laisserait croire qu'il a été pris en compte : envoyer `devise=CDF`
    au domaine crédit chargerait des montants étiquetés USD, sans un mot.
    """
    attendus = set(spec.requis) | set(spec.optionnels)
    donnes = {c: v for c, v in fournis.items()
              if v is not None and not _est_marqueur_fastapi(v)
              and (not isinstance(v, str) or v.strip() != "")}

    en_trop = sorted(set(donnes) - attendus)
    if en_trop:
        raise HTTPException(
            422,
            f"Le domaine « {domaine} » n'accepte pas : {', '.join(en_trop)}. "
            f"Paramètres acceptés : {', '.join(sorted(attendus)) or 'aucun'}.")

    manquants = [c for c in spec.requis if c not in donnes]
    if manquants:
        raise HTTPException(
            422, f"Paramètre(s) obligatoire(s) manquant(s) pour « {domaine} » : "
                 f"{', '.join(manquants)}.")

    kwargs: dict = {}
    for cle, valeur in donnes.items():
        if cle in ("date_arrete", "date_effet"):
            kwargs[cle] = _date(valeur, cle)
        elif cle == "exercice":
            kwargs[cle] = int(valeur)
        elif cle == "devise":
            kwargs[cle] = valeur.strip().upper()
        else:
            kwargs[cle] = valeur.strip()
    return kwargs


def _ecrire_sur_disque(fichier: UploadFile, chemin: str) -> int:
    """Écrit l'envoi par morceaux (jamais tout en mémoire) et applique le plafond."""
    limite = TAILLE_MAX_MO * 1024 * 1024
    total = 0
    with open(chemin, "wb") as sortie:
        while True:
            morceau = fichier.file.read(1024 * 1024)
            if not morceau:
                break
            total += len(morceau)
            if total > limite:
                raise HTTPException(
                    413, f"Fichier trop volumineux (plafond {TAILLE_MAX_MO} Mo). "
                         "Relever POPPILOT_IMPORT_MAX_MO si l'extraction est légitime.")
            sortie.write(morceau)
    if total == 0:
        raise HTTPException(400, "Fichier vide.")
    return total


def _lignes_acceptees(resultat: dict) -> int:
    """Nombre de lignes chargées, quel que soit le vocabulaire du module d'ingestion."""
    #  Chaque module d'ingestion nomme son compteur à sa façon. Un nom absent de
    #  cette liste faisait annoncer « Aucune ligne chargée — vérifier qu'il
    #  s'agit du bon fichier » sur un import qui venait pourtant d'écrire 188
    #  lignes dans Supabase. Le pire des messages : il accuse le fichier de
    #  l'opérateur pour un défaut qui est ici.
    for cle in ("acceptees", "lignes_importees", "objectifs", "comptes"):
        if isinstance(resultat.get(cle), int):
            return resultat[cle]
    return 0


def _tracer(domaine: str, spec: Domaine, kwargs: dict, *, nom_fichier: str,
            login: str, resultat: dict) -> None:
    """Fait apparaître QUI a importé QUOI dans le journal (import_log, règle I-9).

    Les modules d'ingestion journalisent déjà l'essentiel, mais ils ne peuvent pas
    connaître l'appelant : on complète leur ligne. Les deux domaines qui ne
    journalisent pas du tout (objectifs, budget) reçoivent ici leur ligne, sans quoi
    le journal affiché sur le web tairait la moitié des imports.
    """
    aujourdhui = dt.date.today()
    arrete = kwargs.get("date_arrete") or kwargs.get("date_effet")
    if arrete is None and "exercice" in kwargs:   # budget : daté par exercice
        arrete = dt.date(int(kwargs["exercice"]), 1, 1)
    if arrete is None:
        # Domaine sans date (taux : période dans le résultat ; mapping sans date d'effet).
        # Sans ce repli, le journal levait KeyError APRÈS un import réussi → 500 affiché.
        arrete = dt.date.fromisoformat(resultat["au"]) if resultat.get("au") else aujourdhui

    s = get_session()
    try:
        if spec.journalise:
            ligne = s.execute(
                select(ImportLog).where(ImportLog.domaine == domaine,
                                        ImportLog.date_arrete == arrete)
                .order_by(ImportLog.id.desc())
            ).scalars().first()
            if ligne is not None:
                ligne.message = f"{ligne.message or ''} | import web par {login}".strip(" |")
                s.commit()
                return
        s.add(ImportLog(
            domaine=domaine, fichier=nom_fichier,
            date_snapshot=aujourdhui, date_arrete=arrete,
            lignes_acceptees=_lignes_acceptees(resultat), lignes_rejetees=0,
            horodatage=dt.datetime.now(),
            message=f"import web par {login} | {resultat}"[:500],
        ))
        s.commit()
    finally:
        s.close()


@routeur.get("/import/domaines")
def endpoint_domaines(user: dict = Depends(utilisateur_courant)):
    """Ce que l'interface peut proposer à l'import, et ce que chaque domaine réclame."""
    exiger_role(user, ROLES_ECRITURE)
    return {
        "base": cible_base(),
        "taille_max_mo": TAILLE_MAX_MO,
        "domaines": [
            {"cle": cle, "libelle": d.libelle, "extensions": list(d.extensions),
             "requis": list(d.requis), "optionnels": list(d.optionnels), "aide": d.aide}
            for cle, d in DOMAINES.items()
        ],
    }


@routeur.get("/imports")
def endpoint_journal(limite: int = Query(20, ge=1, le=200),
                     user: dict = Depends(utilisateur_courant)):
    """Derniers imports enregistrés — de quoi vérifier ce que la base contient vraiment.

    Ouvert aux rôles à accès total : l'AUDIT doit pouvoir lire le journal des imports
    sans avoir le droit d'en lancer un.
    """
    exiger_role(user, ROLES_ACCES_TOTAL)
    s = get_session()
    try:
        lignes = s.execute(
            select(ImportLog).order_by(ImportLog.id.desc()).limit(limite)
        ).scalars().all()
        return {
            "base": cible_base(),
            "imports": [
                {"domaine": l.domaine, "fichier": l.fichier,
                 "date_arrete": l.date_arrete.isoformat() if l.date_arrete else None,
                 "date_snapshot": l.date_snapshot.isoformat() if l.date_snapshot else None,
                 "acceptees": l.lignes_acceptees, "rejetees": l.lignes_rejetees,
                 "horodatage": l.horodatage.isoformat() if l.horodatage else None,
                 "message": l.message}
                for l in lignes
            ],
        }
    finally:
        s.close()


@routeur.post("/import/{domaine}")
def endpoint_import(domaine: str,
                    fichier: UploadFile = File(..., description="Fichier exporté du CBS"),
                    date_arrete: str | None = Form(None, description="AAAA-MM-JJ"),
                    date_effet: str | None = Form(None, description="AAAA-MM-JJ"),
                    feuille: str | None = Form(None),
                    # Le mapping budgétaire vient d'un classeur tenu à la main :
                    # ses deux onglets peuvent être nommés autrement que par défaut.
                    feuille_charges: str | None = Form(None),
                    feuille_produits: str | None = Form(None),
                    devise: str | None = Form(None),
                    exercice: int | None = Form(None),
                    hypothese: str | None = Form(None),
                    user: dict = Depends(utilisateur_courant)):
    """Charge un fichier du CBS dans le socle. Réservé à DIRECTION / CDG.

    Idempotent : ré-importer le même arrêté REMPLACE le snapshot précédent (jamais de
    doublon). Le nombre de lignes ainsi purgées est renvoyé — c'est la seule façon de
    voir qu'on vient d'écraser un import antérieur.
    """
    exiger_role(user, ROLES_ECRITURE)

    spec = DOMAINES.get(domaine)
    if spec is None:
        raise HTTPException(
            404, f"Domaine d'import inconnu : {domaine!r}. "
                 f"Domaines disponibles : {', '.join(DOMAINES)}.")

    # Un .env au gabarit ne pointe sur rien : l'import échouerait sur une erreur DNS
    # incompréhensible, ou pire, atterrirait dans la base SQLite locale.
    gabarit = env_encore_gabarit()
    if gabarit:
        raise HTTPException(503, f"Import refusé — configuration incomplète : {gabarit}")

    kwargs = _parametres(domaine, spec, {
        "date_arrete": date_arrete, "date_effet": date_effet, "feuille": feuille,
        "feuille_charges": feuille_charges, "feuille_produits": feuille_produits,
        "devise": devise, "exercice": exercice, "hypothese": hypothese,
    })
    nom = _nom_sain(fichier.filename, spec.extensions)

    # Dossier temporaire dédié : le fichier y garde son nom d'origine (qui part dans
    # import_log) sans jamais pouvoir écraser quoi que ce soit d'autre.
    dossier = tempfile.mkdtemp(prefix="poppilot_import_")
    chemin = os.path.join(dossier, nom)
    try:
        octets = _ecrire_sur_disque(fichier, chemin)
        try:
            resultat = spec.fonction(chemin, **kwargs)
        except HTTPException:
            raise
        except ERREURS_DE_FICHIER as e:
            # Le gestionnaire ValueError global traduirait ceci en 404 « donnée absente » :
            # ici la donnée n'est pas absente, c'est le fichier qui ne convient pas.
            raise HTTPException(400, f"Fichier refusé par l'import « {domaine} » : {e}")
    finally:
        shutil.rmtree(dossier, ignore_errors=True)

    _tracer(domaine, spec, kwargs, nom_fichier=nom, login=user["login"], resultat=resultat)

    return {
        "domaine": domaine, "libelle": spec.libelle,
        "fichier": nom, "octets": octets,
        "parametres": {c: (v.isoformat() if isinstance(v, dt.date) else v)
                       for c, v in kwargs.items()},
        "resultat": resultat,
        "lignes_chargees": _lignes_acceptees(resultat),
        "base": cible_base(),
        "importe_par": user["login"],
    }
