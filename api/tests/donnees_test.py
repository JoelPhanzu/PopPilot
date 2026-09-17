"""
Localisation des fichiers sources de validation + exécution HONNÊTE des tests.

DEUX PROBLÈMES QUE CE MODULE RÈGLE
----------------------------------
1. Les chemins étaient codés en dur en « /mnt/user-data/uploads/… » (un environnement
   Linux d'une session précédente). Sur la machine du CDG, aucun n'existe : plus aucun
   test de validation ne pouvait tourner.

2. Pire : quand un fichier manquait, le test faisait « return » en silence et le bloc
   __main__ imprimait quand même « ✓ » puis « Phase 1 validée ». La suite était donc
   VERTE alors que RIEN n'avait été vérifié. Dans un projet dont la valeur tient à
   l'écart nul contre les fichiers réels, un faux vert est pire que pas de test.
   → `lancer()` distingue PASSÉ / SAUTÉ / ÉCHOUÉ et refuse de conclure « validé »
     si quoi que ce soit a été sauté.

OÙ METTRE LES FICHIERS SOURCES
------------------------------
Ce sont de vraies données clients : elles ne vont JAMAIS dans git (.gitignore couvre
`data_local/`). Deux possibilités :
  - les déposer dans   PopPilot/data_local/
  - ou pointer ailleurs :  set POPPILOT_DONNEES=D:/chemin/vers/les/extractions
"""
from __future__ import annotations

import os
import sys

_ICI = os.path.dirname(os.path.abspath(__file__))
_RACINE = os.path.dirname(os.path.dirname(_ICI))          # …/PopPilot

# Console Windows en cp1252 : sans cela, le moindre « ✓ » dans un message de test
# lève UnicodeEncodeError et le test s'interrompt AVANT de rendre son verdict.
sys.path.insert(0, os.path.dirname(_ICI))
from socle.console import activer_utf8  # noqa: E402

activer_utf8()


class TestSaute(Exception):
    """Levée quand un test ne peut pas s'exécuter (source absente). Pas un échec."""


def dossier_donnees() -> str:
    """Dossier des fichiers sources réels (hors dépôt)."""
    return os.environ.get("POPPILOT_DONNEES") or os.path.join(_RACINE, "data_local")


def fichier(nom: str) -> str | None:
    """Chemin d'un fichier source s'il est présent, sinon None.

    Tolère les anciens chemins absolus (« /mnt/user-data/uploads/x.xls ») : seul le
    nom de base est retenu, puis cherché dans le dossier de données.
    """
    base = os.path.basename(nom.replace("\\", "/"))
    chemin = os.path.join(dossier_donnees(), base)
    return chemin if os.path.exists(chemin) else None


def exiger(nom: str) -> str:
    """Chemin du fichier, ou saute le test en expliquant ce qui manque et où le mettre."""
    chemin = fichier(nom)
    if chemin is None:
        raise TestSaute(f"source absente : {os.path.basename(nom)} "
                        f"(attendue dans {dossier_donnees()})")
    return chemin


def exiger_un_de(*noms: str) -> str:
    """Chemin du premier fichier présent parmi plusieurs variantes acceptables.

    Le CBS exporte le même inventaire tantôt en .csv tantôt en .xlsx : le test doit
    accepter l'un OU l'autre plutôt que d'exiger une extension précise.
    """
    for nom in noms:
        chemin = fichier(nom)
        if chemin is not None:
            return chemin
    raise TestSaute("aucune de ces sources : " + ", ".join(os.path.basename(n) for n in noms)
                    + f" (attendues dans {dossier_donnees()})")


# Codes de sortie d'une suite. Ils sont LE signal : `lancer_tous.py` s'en sert pour
# rendre son verdict, au lieu de chercher un mot dans le texte imprimé.
#
# POURQUOI : la campagne classait une suite en cherchant « NON VALIDE » dans sa sortie.
# Une suite PARTIELLE (des cas passés, d'autres sautés faute de source) imprime
# « PARTIEL », jamais « NON VALIDE » : elle était donc promue VALIDE, et la campagne
# concluait « TOUT VALIDE : ecart nul contre les fichiers reels » alors qu'un cas
# n'avait jamais été exécuté. C'est exactement le faux vert que ce module existe pour
# empêcher. Un code de sortie ne se laisse pas paraphraser.
VALIDE, ECHEC, RIEN_VERIFIE, PARTIEL = 0, 1, 2, 3


def lancer(titre: str, cas: list[tuple]) -> int:
    """Exécute les cas et rend un compte rendu qui ne ment pas.

    `cas` : liste de (fonction, libellé). Renvoie un code de sortie :
      0 VALIDE       — tout est passé, aucun saut.
      1 ECHEC        — au moins un écart : ne livrer aucun chiffre.
      2 RIEN_VERIFIE — tout a été sauté (sources absentes) : ce n'est PAS un succès.
      3 PARTIEL      — une partie vérifiée, une partie sautée : PAS validé non plus.
    Un test sauté n'est pas un échec, mais interdit d'annoncer la phase comme validée.
    """
    passes, sautes, echecs = [], [], []
    for fn, libelle in cas:
        try:
            fn()
            passes.append(libelle)
            print(f"  [OK]    {libelle}")
        except TestSaute as e:
            sautes.append(libelle)
            print(f"  [SAUTE] {libelle} — {e}")
        except AssertionError as e:
            echecs.append(libelle)
            print(f"  [ECHEC] {libelle} — {e}")
        except Exception as e:                       # noqa: BLE001
            echecs.append(libelle)
            print(f"  [ERREUR] {libelle} — {type(e).__name__}: {e}")

    print(f"\n{titre} : {len(passes)} passé(s), {len(sautes)} sauté(s), {len(echecs)} échec(s)")
    if echecs:
        print(f"  >>> {titre} EN ECHEC — ne pas livrer de chiffres sur cette base.")
        return ECHEC
    if sautes and passes:
        print(f"  >>> {titre} PARTIEL : {len(passes)} cas verifies, "
              f"{len(sautes)} NON verifies (sources absentes).")
        for libelle in sautes:
            print(f"        non verifie : {libelle}")
        print(f"      Deposer les sources manquantes dans : {dossier_donnees()}")
        return PARTIEL
    if sautes:
        print(f"  >>> {titre} NON VALIDE : fichiers sources absents, rien n'a ete verifie.")
        print(f"      Deposer les extractions dans : {dossier_donnees()}")
        print( "      (ou definir POPPILOT_DONNEES vers le dossier qui les contient)")
        return RIEN_VERIFIE
    print(f"  >>> {titre} VALIDE : {len(passes)} cas verifies, aucun saut.")
    return VALIDE


def sortir(code: int):
    sys.exit(code)
