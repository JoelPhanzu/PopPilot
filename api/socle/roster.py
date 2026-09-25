"""
Rapprochement des noms du roster (fichier OBJECTIF) avec les noms de l'extraction CBS.

POURQUOI : le fichier OBJECTIF écrit les superviseurs en NOM COURT (« KANDA RODDY ») alors que
le CBS porte le nom complet (« MBOLELA KANDA RODDY »). Comparés à l'identique, aucun superviseur
ne correspondait : tous leurs portefeuilles tombaient en « orphelin » (constat de mai 2026).

RÈGLE (dans une même agence, sans tenir compte de la casse ni de l'ordre des mots) :
  1. nom identique → correspondance ;
  2. sinon, tous les mots du nom du roster figurent dans le nom CBS (ou l'inverse) ET un seul
     nom du roster de l'agence remplit cette condition → correspondance ;
  3. sinon (aucun ou plusieurs candidats) → pas de correspondance : le portefeuille reste
     orphelin. On ne devine jamais entre deux homonymes.
"""
from __future__ import annotations


def _maj(t) -> str:
    return " ".join((t or "").split()).upper()


normaliser = _maj   # clé de comparaison commune : casse et espaces multiples ignorés


def _mots(t) -> frozenset:
    return frozenset(_maj(t).split())


def correspondances(roster: set[tuple[str, str]], noms_cbs) -> dict[tuple[str, str], tuple[str, str]]:
    """roster : {(NOM, AGENCE)} en majuscules. noms_cbs : itérable de (nom, agence) du CBS.
    Renvoie {(NOM_CBS, AGENCE): (NOM_ROSTER, AGENCE)} pour chaque nom CBS rattaché."""
    par_agence: dict[str, list] = {}
    for nom, agence in roster:
        par_agence.setdefault(_maj(agence), []).append((_maj(nom), _mots(nom)))
    resultat = {}
    for nom, agence in {(_maj(n), _maj(a)) for n, a in noms_cbs if n}:
        candidats = par_agence.get(agence, [])
        exact = [r for r, _ in candidats if r == nom]
        if exact:
            resultat[(nom, agence)] = (exact[0], agence)
            continue
        mots = _mots(nom)
        inclus = [r for r, m in candidats if m and (m <= mots or mots <= m)]
        if len(inclus) == 1:
            resultat[(nom, agence)] = (inclus[0], agence)
    return resultat
