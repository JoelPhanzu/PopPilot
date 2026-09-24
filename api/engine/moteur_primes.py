"""
Moteur de calcul des primes — agents de crédit & superviseurs (chantier 4).
Fidèle au fichier CALCUL_PRIMES (feuille "AC et SUP"). Testé au centime.

⚠️ La prime NE dépend PAS des intérêts. Elle se calcule sur : volume décaissé, nombre de
décaissements, encours, épargne (couverture), PAR30, type de produit (GL/IL).

BARÈME (paramètres, en base param_bareme_prime — datés) :
  prime_volume=150, prime_nombre=90, prime_couverture=60
  seuil_volume=100%, seuil_nombre=80%, seuil_couverture=29,5%
  correcteur PAR : ≤3%→×1 ; 3-5%→×0,7 ; 5-7%→×0,5 ; >7%→×0

CASCADE DE CALCUL (par agent) :
1. Éligibilité encours : IL → encours>=100000 ET nb>=25 ; GL → encours>=50000 ET nb>=100.
2. Type de prime : Volume>=100% & Nombre>=80% → "Volume+Nombre" ; Volume>=100% → "Volume" ;
   Nombre>=80% → "Nombre" ; sinon "Aucune prime".
3. Prime crédit = (240 si V+N ; 150 si V ; 90 si N) × coefficient PAR.
4. Prime couverture = 60 si taux_couverture (épargne/encours) >= 29,5% sinon 0.
5. Prime totale = crédit + couverture. + motif explicatif.

Le PAR30 par agent vient du moteur crédit (source unique), jamais ressaisi.
STRICTEMENT ADDITIF.
"""
from __future__ import annotations
from dataclasses import dataclass, field

# barème par défaut (à lire depuis param_bareme_prime en production)
BAREME = {
    "prime_volume": 150, "prime_nombre": 90, "prime_couverture": 60,
    "seuil_volume": 1.0, "seuil_nombre": 0.8, "seuil_couverture": 0.295,
    "par_tranches": [(0.03, 1.0), (0.05, 0.7), (0.07, 0.5), (float("inf"), 0.0)],
    "elig_IL": {"encours": 100000, "nombre": 25},
    "elig_GL": {"encours": 50000, "nombre": 100},
}


def coefficient_par(par30: float, bareme=BAREME) -> float:
    """Correcteur PAR : ≤3%→1 ; 3-5%→0,7 ; 5-7%→0,5 ; >7%→0."""
    if par30 is None:
        return 1.0
    for seuil, coeff in bareme["par_tranches"]:
        if par30 <= seuil:
            return coeff
    return 0.0


def calculer_prime_agent(*, produit, volume_realise, volume_objectif,
                         nombre_realise, nombre_objectif, encours_volume, encours_nombre,
                         solde_epargne, par30, bareme=BAREME):
    """Calcule la prime d'un agent. produit = 'GL' ou 'IL'. Renvoie le détail complet."""
    # taux de réalisation
    taux_volume = (volume_realise / volume_objectif) if volume_objectif else 0.0
    taux_nombre = (nombre_realise / nombre_objectif) if nombre_objectif else 0.0
    taux_couverture = round(solde_epargne / encours_volume, 3) if encours_volume else 0.0

    # 1. éligibilité encours
    elig = bareme["elig_IL"] if produit == "IL" else bareme["elig_GL"]
    eligible = encours_volume >= elig["encours"] and encours_nombre >= elig["nombre"]

    # 2. type de prime
    if not eligible:
        type_prime = "Non éligible"
    elif taux_volume >= bareme["seuil_volume"] and taux_nombre >= bareme["seuil_nombre"]:
        type_prime = "Volume + Nombre"
    elif taux_volume >= bareme["seuil_volume"]:
        type_prime = "Volume"
    elif taux_nombre >= bareme["seuil_nombre"]:
        type_prime = "Nombre"
    else:
        type_prime = "Aucune prime"

    # 3. prime crédit × coefficient PAR
    coeff = coefficient_par(par30, bareme)
    base_credit = {"Volume + Nombre": bareme["prime_volume"] + bareme["prime_nombre"],
                   "Volume": bareme["prime_volume"], "Nombre": bareme["prime_nombre"]}.get(type_prime, 0)
    prime_credit = base_credit * coeff

    # 4. prime couverture (indépendante du PAR)
    prime_couverture = bareme["prime_couverture"] if taux_couverture >= bareme["seuil_couverture"] else 0

    # 5. total + motif
    prime_totale = prime_credit + prime_couverture
    motifs = []
    if taux_volume < bareme["seuil_volume"]:
        motifs.append("Volume inférieur à 100%")
    if taux_nombre < bareme["seuil_nombre"]:
        motifs.append("Nombre inférieur à 80%")
    if type_prime not in ("Non éligible",) and coeff == 0:
        motifs.append("PAR > 7% (crédit annulé)")
    elif type_prime not in ("Non éligible",) and 0 < coeff < 1:
        motifs.append("PAR entre 3% et 7% (crédit réduit)")
    if taux_couverture < bareme["seuil_couverture"]:
        motifs.append("Couverture inférieure à 30%")
    if not eligible:
        motifs.append("Encours sous le seuil d'éligibilité")
    motif = "Prime complète" if not motifs else " ; ".join(motifs)

    return {
        "produit": produit,
        "taux_volume": taux_volume, "taux_nombre": taux_nombre,
        "taux_couverture": taux_couverture, "eligible": eligible,
        "type_prime": type_prime, "coefficient_par": coeff,
        "prime_credit": round(prime_credit, 2),
        "prime_couverture": round(prime_couverture, 2),
        "prime_totale": round(prime_totale, 2),
        "motif": motif,
    }


if __name__ == "__main__":
    # test contre le fichier de mai : BAZOMBWA BELI FRANK (IL) → Volume, crédit 105, couv 60, total 165
    r = calculer_prime_agent(
        produit="IL", volume_realise=95400, volume_objectif=57029,
        nombre_realise=8, nombre_objectif=12,
        encours_volume=605741.15, encours_nombre=61,
        solde_epargne=180970.76, par30=0.0334)
    print("BAZOMBWA BELI FRANK (IL) :")
    print(f"  type={r['type_prime']} coeff_PAR={r['coefficient_par']} "
          f"crédit={r['prime_credit']} couv={r['prime_couverture']} TOTALE={r['prime_totale']}")
    print(f"  motif : {r['motif']}")
    print(f"  → référence fichier : Volume, crédit 105, couv 60, total 165")
    ok = (r['prime_credit'] == 105 and r['prime_couverture'] == 60 and r['prime_totale'] == 165)
    print("  VALIDATION :", "✓ EXACT" if ok else "✗ écart")


# ============================================================
# AUTRES CATÉGORIES DE PERSONNEL (fidèle au fichier CALCUL_PRIMES)
# ============================================================

def prime_superviseur_epargne(realisation, paliers=None):
    """Prime superviseur épargne = palier selon le MONTANT d'épargne réalisé (LOOKUP).
    Paliers par défaut : ≥50k→60 ; ≥70k→100 ; ≥100k→200 ; sinon 0."""
    paliers = paliers or [(100000, 200), (70000, 100), (50000, 60), (0, 0)]
    for seuil, prime in paliers:
        if realisation >= seuil:
            return {"realisation": realisation, "prime": prime}
    return {"realisation": realisation, "prime": 0}


def prime_recouvrement(montant_91_180, montant_181_plus, montant_radie, *, agent=True):
    """Prime recouvrement = taux × montant recouvré selon l'ancienneté.
    Agents : 1% / 3% / 5%. Responsable : 0,3% / 0,5% / 1%.
    Plus le crédit est difficile (ancien/radié), plus le taux est élevé."""
    if agent:
        t1, t2, t3 = 0.01, 0.03, 0.05
    else:
        t1, t2, t3 = 0.003, 0.005, 0.01
    prime = montant_91_180 * t1 + montant_181_plus * t2 + montant_radie * t3
    return {"prime": round(prime, 2),
            "detail": {"91-180": round(montant_91_180 * t1, 2),
                       "181+": round(montant_181_plus * t2, 2),
                       "radié": round(montant_radie * t3, 2)}}


BAREME_SUPPORT = {
    "prime_volume": 5, "prime_couverture": 10, "seuil_couverture": 0.6, "prime_max": 45,
    "par_tranches": [(0.03, 30), (0.05, 20), (0.07, 10), (float("inf"), 0)],
}


def prime_fonction_support(taux_decaissement, par_agence, taux_couverture,
                           nb_agences, bareme=BAREME_SUPPORT):
    """Prime fonctions support (superviseurs siège) : par agence supervisée.
    Prime unitaire = prime_volume (si décaissement atteint) + prime_PAR (selon PAR)
    + prime_couverture (si couverture atteinte). Puis × nombre d'agences supervisées.
    NB : dans le fichier, N = somme des 3 primes unitaires, O = N × nb_agences."""
    pv = bareme["prime_volume"] if taux_decaissement >= 1.0 else 0
    # prime PAR : palier selon le PAR de l'agence
    ppar = 0
    for seuil, montant in bareme["par_tranches"]:
        if par_agence <= seuil:
            ppar = montant
            break
    pc = bareme["prime_couverture"] if taux_couverture >= bareme["seuil_couverture"] else 0
    prime_unitaire = pv + ppar + pc
    prime_totale = prime_unitaire * nb_agences
    return {"prime_volume": pv, "prime_par": ppar, "prime_couverture": pc,
            "prime_unitaire": prime_unitaire, "nb_agences": nb_agences,
            "prime_totale": round(prime_totale, 2)}


def prime_direction_agence(resultat_comptable, taux_directeur=0.01, taux_adjoint=0.005):
    """Prime direction d'agence = % du RÉSULTAT COMPTABLE de l'agence.
    Directeur 1%, Adjoint 0,5%. Pas de prime si résultat négatif."""
    base = max(resultat_comptable, 0)
    return {"resultat": resultat_comptable,
            "prime_directeur": round(base * taux_directeur, 2),
            "prime_adjoint": round(base * taux_adjoint, 2)}


def prime_direction(profitabilite_globale, fonctions=None):
    """Prime direction (siège) = % de la profitabilité globale de l'institution.
    Taux par fonction (ex. DG 1%, Dir. crédit 0,6%, DAF 0,3%)."""
    fonctions = fonctions or {"Directeur Général": 0.01, "Directeur des opérations": 0.006,
                              "Directeur Administratif et Financier": 0.003}
    base = max(profitabilite_globale, 0)
    return {f: round(base * t, 2) for f, t in fonctions.items()}
