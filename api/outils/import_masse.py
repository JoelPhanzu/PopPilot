"""
PopPilot — import EN MASSE des fichiers lourds, sans passer par le site.

    cd api
    .venv\\Scripts\\python.exe outils\\import_masse.py "D:\\Inventaires" --a-blanc
    .venv\\Scripts\\python.exe outils\\import_masse.py "D:\\Inventaires"

Pourquoi ce script plutôt que du SQL brut (COPY, éditeur Supabase, pgAdmin) : il appelle
EXACTEMENT la fonction d'import du site (ingest/import_epargne.py, ingest/import_credit.py).
Les règles restent donc appliquées — classement à vue / à terme / obligatoire, groupes,
purge du mois avant réécriture (jamais de doublon), journal des imports (page Import).
Une insertion SQL directe contournerait tout cela : chiffres faux, sans alerte.

FONCTIONNEMENT
  - un DOSSIER de fichiers ; le MOIS de chaque fichier est lu dans son NOM (« Inventaire
    dépôt Janvier 2025.csv », « inventaire_2025-01.xlsx », « 01-2025 »…) ; date d'arrêté =
    dernier jour du mois (la date d'arrêté fait foi, CLAUDE.md §69.2) ;
  - un nom sans mois, ou avec DEUX mois, est REFUSÉ : on ne devine pas. Le préciser alors
    dans un fichier de correspondance (--correspondance, lignes « nom du fichier;AAAA-MM ») ;
  - deux fichiers pour le même mois → refus avant toute écriture ;
  - --a-blanc : vérifie tout (mois, en-têtes, nombre de lignes) et N'ÉCRIT RIEN ;
  - import un mois à la fois, du plus ancien au plus récent ; chaque mois est validé
    (commit) avant le suivant : une coupure ne perd que le mois en cours ;
  - REPRISE : un mois déjà en base est SAUTÉ (relancer après une coupure reprend où l'on
    s'était arrêté) ; --remplacer pour le réimporter quand même ;
  - la base visée est celle de api/.env (DATABASE_URL) : elle est AFFICHÉE et doit être
    confirmée en tapant OUI (ou --oui pour un lancement sans surveillance).

Domaines : epargne (inventaire dépôt, .csv / .xlsx) — par défaut ; credit (extraction A→AF).
"""
from __future__ import annotations

import argparse
import calendar
import datetime as dt
import os
import re
import sys
import time
import unicodedata

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(ICI))           # api/

MOIS = {
    "janvier": 1, "janv": 1, "jan": 1,
    "fevrier": 2, "fevr": 2, "fev": 2,
    "mars": 3, "mar": 3,
    "avril": 4, "avr": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7, "juil": 7,
    "aout": 8,
    "septembre": 9, "sept": 9, "sep": 9,
    "octobre": 10, "oct": 10,
    "novembre": 11, "nov": 11,
    "decembre": 12, "dec": 12,
}
BASE: str | None = None        # --base-sqlite : fichier SQLite visé à la place de api/.env

EXTENSIONS = {"epargne": (".csv", ".xlsx", ".xlsm"), "credit": (".xlsx", ".xlsm", ".xls")}


def _norm(t: str) -> str:
    return unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode().lower()


def fin_de_mois(annee: int, mois: int) -> dt.date:
    return dt.date(annee, mois, calendar.monthrange(annee, mois)[1])


def mois_du_nom(nom: str) -> dt.date:
    """Date d'arrêté (fin de mois) lue dans le nom du fichier ; ValueError si absent/ambigu."""
    base = _norm(os.path.splitext(nom)[0])
    trouves: set[tuple[int, int]] = set()
    mots = re.findall(r"[a-z]+|\d+", base)
    for i, m in enumerate(mots):                           # « janvier 2025 », « jan_25 »
        if m in MOIS:
            for voisin in mots[i + 1:i + 3]:
                if voisin.isdigit() and len(voisin) in (2, 4):
                    a = int(voisin) + (2000 if len(voisin) == 2 else 0)
                    if 2015 <= a <= 2100:
                        trouves.add((a, MOIS[m]))
                    break
    for a, m in re.findall(r"(20\d\d)[-_. ]?(0[1-9]|1[0-2])(?!\d)", base):   # 2025-01, 202501
        trouves.add((int(a), int(m)))
    for m, a in re.findall(r"(?<!\d)(0[1-9]|1[0-2])[-_. ](20\d\d)", base):   # 01-2025
        trouves.add((int(a), int(m)))
    if not trouves:
        raise ValueError("aucun mois reconnu dans le nom")
    if len(trouves) > 1:
        liste = ", ".join(f"{m:02d}/{a}" for a, m in sorted(trouves))
        raise ValueError(f"plusieurs mois possibles ({liste})")
    a, m = trouves.pop()
    return fin_de_mois(a, m)


def lire_correspondance(chemin: str) -> dict[str, dt.date]:
    """Fichier texte « nom du fichier;AAAA-MM » (une ligne par fichier, # = commentaire)."""
    table = {}
    with open(chemin, encoding="utf-8-sig") as f:
        for n, ligne in enumerate(f, 1):
            ligne = ligne.strip()
            if not ligne or ligne.startswith("#"):
                continue
            try:
                nom, mois = [x.strip() for x in ligne.split(";")]
                a, m = (int(x) for x in mois.split("-"))
                table[nom] = fin_de_mois(a, m)
            except ValueError:
                raise SystemExit(f"Correspondance, ligne {n} illisible : {ligne!r} "
                                 "(attendu : nom du fichier;AAAA-MM)")
    return table


def verifier_fichier(domaine: str, chemin: str) -> int:
    """Contrôle à blanc : en-têtes attendus + nombre de lignes. Lève ValueError sinon."""
    if domaine == "epargne":
        from ingest.import_epargne import lignes_inventaire, verifier_colonnes
        n = 0
        for ligne in lignes_inventaire(chemin):
            if n == 0:
                verifier_colonnes(ligne)
                if "id_cpte" not in ligne:
                    raise ValueError("colonne id_cpte absente")
            if ligne.get("id_cpte"):
                n += 1
        if n == 0:
            raise ValueError("aucun compte lu")
        return n
    from ingest.import_credit import _ouvrir
    wb = _ouvrir(chemin)
    ws = wb["Worksheet"] if "Worksheet" in wb.sheetnames else wb.worksheets[0]
    lignes = ws.iter_rows(values_only=True)
    entete = next(lignes)
    if len(entete) < 2 or entete[1] is None or "dossier" not in str(entete[1]).lower():
        raise ValueError(f"en-tête inattendu (colonne 2 = {entete[1] if len(entete) > 1 else None!r}) : "
                         "extraction crédit A→AF attendue")
    return sum(1 for r in lignes if len(r) > 1 and r[1] not in (None, ""))


def deja_en_base(domaine: str, date_arrete: dt.date) -> int:
    from sqlalchemy import func, select
    from socle.schema import FaitCredit, FaitEpargne, get_session
    table = FaitEpargne if domaine == "epargne" else FaitCredit
    s = get_session(BASE) if BASE else get_session()
    try:
        return s.execute(select(func.count()).select_from(table)
                         .where(table.date_arrete == date_arrete)).scalar_one()
    finally:
        s.close()


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Import en masse des fichiers lourds (sans le site).")
    p.add_argument("dossier", help="dossier contenant les fichiers")
    p.add_argument("--domaine", choices=("epargne", "credit"), default="epargne")
    p.add_argument("--a-blanc", action="store_true", help="tout vérifier, ne rien écrire")
    p.add_argument("--remplacer", action="store_true", help="réimporter les mois déjà en base")
    p.add_argument("--correspondance", help="fichier « nom;AAAA-MM » pour les noms sans mois clair")
    p.add_argument("--oui", action="store_true", help="ne pas demander de confirmation")
    p.add_argument("--base-sqlite", help="essai sur un fichier SQLite local au lieu de api/.env")
    args = p.parse_args(argv)

    global BASE
    from socle.schema import cible_base as _cible, env_encore_gabarit
    BASE = args.base_sqlite
    cible_base = (lambda: f"SQLite local d'essai ({BASE})") if BASE else _cible
    if BASE:
        from socle.schema import init_db
        init_db(BASE)
    gabarit = None if BASE else env_encore_gabarit()
    if gabarit:
        print(f"REFUS : {gabarit}")
        return 2
    if not os.path.isdir(args.dossier):
        print(f"REFUS : dossier introuvable : {args.dossier}")
        return 2

    correspondance = lire_correspondance(args.correspondance) if args.correspondance else {}
    fichiers = sorted(f for f in os.listdir(args.dossier)
                      if f.lower().endswith(EXTENSIONS[args.domaine]) and not f.startswith("~$"))
    if not fichiers:
        print(f"Aucun fichier {', '.join(EXTENSIONS[args.domaine])} dans {args.dossier}")
        return 2

    # 1. Mois de chaque fichier — tout est résolu AVANT la moindre écriture.
    plan, erreurs = [], []
    for f in fichiers:
        try:
            d = correspondance.get(f) or mois_du_nom(f)
            plan.append((d, f))
        except ValueError as e:
            erreurs.append(f"  {f} : {e} → le préciser dans --correspondance")
    par_mois: dict[dt.date, list[str]] = {}
    for d, f in plan:
        par_mois.setdefault(d, []).append(f)
    for d, fs in par_mois.items():
        if len(fs) > 1:
            erreurs.append(f"  {d:%m/%Y} : plusieurs fichiers ({' | '.join(fs)})")
    print(f"Base visée : {cible_base()}")
    print(f"Domaine    : {args.domaine} — {len(fichiers)} fichier(s) dans {args.dossier}")
    if erreurs:
        print("REFUS — noms de fichiers à clarifier, rien n'a été importé :")
        print("\n".join(erreurs))
        return 1
    plan.sort()

    # 2. État de la base et plan.
    print(f"\n{'Mois':8} {'Arrêté':11} {'En base':>9}  Action   Fichier")
    a_faire = []
    for d, f in plan:
        n = deja_en_base(args.domaine, d)
        action = "remplace" if n and args.remplacer else ("saute" if n else "importe")
        if action != "saute":
            a_faire.append((d, f))
        print(f"{d:%m/%Y}  {d.isoformat()} {n:>9,}  {action:8} {f}".replace(",", " "))

    if args.a_blanc:
        print("\nMODE À BLANC : contrôle des fichiers (en-têtes, nombre de lignes), rien n'est écrit.")
        ko = 0
        for d, f in a_faire:
            t0 = time.time()
            try:
                n = verifier_fichier(args.domaine, os.path.join(args.dossier, f))
                print(f"  OK   {d:%m/%Y}  {n:>9,} lignes  ({time.time() - t0:.0f} s)  {f}".replace(",", " "))
            except Exception as e:                                  # noqa: BLE001
                ko += 1
                print(f"  KO   {d:%m/%Y}  {f} : {e}")
        print(f"\n{len(a_faire) - ko} fichier(s) prêt(s), {ko} en erreur."
              + (" Corriger avant l'import réel." if ko else " Relancer sans --a-blanc pour importer."))
        return 1 if ko else 0

    if not a_faire:
        print("\nRien à importer (tous les mois sont déjà en base ; --remplacer pour les refaire).")
        return 0
    if not args.oui:
        rep = input(f"\nImporter {len(a_faire)} mois dans {cible_base()} ? Taper OUI : ")
        if rep.strip().upper() != "OUI":
            print("Abandon : rien n'a été importé.")
            return 1

    # 3. Import, un mois à la fois (chaque mois est validé avant le suivant).
    if args.domaine == "epargne":
        from ingest.import_epargne import importer_epargne as importer
    else:
        from ingest.import_credit import importer_credit as importer
    faits, echecs, debut = [], [], time.time()
    for i, (d, f) in enumerate(a_faire, 1):
        chemin = os.path.join(args.dossier, f)
        t0 = time.time()
        print(f"[{i}/{len(a_faire)}] {d:%m/%Y} — {f} …", flush=True)
        try:
            verifier_fichier(args.domaine, chemin)               # format, avant de purger
            r = importer(chemin, d, db_path=BASE) if BASE else importer(chemin, d)
            n = r.get("acceptees", r.get("lignes_acceptees"))
            faits.append(d)
            print(f"        {n:,} lignes, {r.get('purges', 0):,} remplacées, "
                  f"{time.time() - t0:.0f} s".replace(",", " "), flush=True)
        except KeyboardInterrupt:
            print("\nInterrompu : les mois terminés sont en base ; relancer pour reprendre.")
            break
        except Exception as e:                                      # noqa: BLE001
            echecs.append((d, f, e))
            print(f"        ÉCHEC : {e}", flush=True)

    print(f"\nTerminé en {(time.time() - debut) / 60:.1f} min : {len(faits)} mois importé(s), "
          f"{len(echecs)} échec(s).")
    for d, f, e in echecs:
        print(f"  ÉCHEC {d:%m/%Y} {f} : {e}")
    return 1 if echecs else 0


if __name__ == "__main__":
    sys.exit(main())
