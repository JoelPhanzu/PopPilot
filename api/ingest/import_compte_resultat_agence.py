"""
Import du compte de résultat PAR AGENCE (chantier 3) → table compte_resultat_agence.

La lecture et le contrôle sont ceux du moteur fourni (engine/import_compte_resultat_agence :
feuille Feuil2, colonne A = poste, agences reconnues par l'en-tête jusqu'à MICROPOP). Ce module ne fait que
les ÉCRIRE, avec les règles d'import du socle :
  - idempotent (I-4) : réimporter un mois remplace ce mois, et seulement lui ;
  - INTÉGRITÉ : si la colonne MICROPOP ≠ somme des agences sur un poste, on REFUSE
    l'import (ValueError → 400). Un compte de résultat incohérent chargé « avec alerte »
    finirait dans les primes de direction sans que personne relise l'alerte.
  - journalisé dans import_log (I-9).
"""
from __future__ import annotations

import datetime as dt
import os

from socle.schema import CompteResultatAgence, ImportLog, get_session, init_db
from engine.import_compte_resultat_agence import importer_compte_resultat


def importer_compte_resultat_agence(path, date_arrete: dt.date, feuille: str | None = None,
                                    db_path="socle/micropop.db") -> dict:
    r = importer_compte_resultat(path, date_arrete, feuille=feuille or "Feuil2")
    if r["controles_incoherents"]:
        detail = " ; ".join(f"{c['poste']} : MICROPOP {c['consolide']:,.2f} ≠ Σ agences "
                            f"{c['somme_agences']:,.2f}" for c in r["controles_incoherents"][:5])
        raise ValueError(f"Compte de résultat incohérent ({r['nb_alertes']} poste(s)) — {detail}")
    if not any("RESULTAT" in l["poste"].upper() and "COMPTABLE" in l["poste"].upper()
               for l in r["lignes"]):
        raise ValueError("Ligne « RESULTAT COMPTABLE » introuvable : ce n'est pas le "
                         "compte de résultat isolé par agence attendu (feuille Feuil2).")

    init_db(db_path)
    s = get_session(db_path)
    try:
        purges = s.query(CompteResultatAgence).filter(
            CompteResultatAgence.date_arrete == date_arrete).delete()
        # Un poste peut apparaître deux fois dans le fichier (même intitulé dans deux
        # blocs) : la contrainte unique (arrêté, poste, agence) l'interdit. On garde la
        # DERNIÈRE occurrence et on le dit, plutôt que d'échouer sur une erreur SQL.
        uniques: dict[tuple, dict] = {}
        for l in r["lignes"]:
            uniques[(l["poste"], l["agence"])] = l
        doublons = len(r["lignes"]) - len(uniques)
        s.add_all(CompteResultatAgence(date_arrete=date_arrete, poste=l["poste"],
                                       agence=l["agence"], montant=l["montant"], devise="USD")
                  for l in uniques.values())
        s.add(ImportLog(domaine="compte_resultat_agence", fichier=os.path.basename(str(path)),
                        date_snapshot=dt.date.today(), date_arrete=date_arrete,
                        lignes_acceptees=len(uniques), lignes_rejetees=0,
                        horodatage=dt.datetime.now(),
                        message=f"{len(uniques)} lignes, {purges} remplacées"
                                + (f", {doublons} poste(s) en double" if doublons else "")))
        s.commit()
    finally:
        s.close()
    return {"lignes_importees": len(uniques), "remplacees": purges, "postes_en_double": doublons}
