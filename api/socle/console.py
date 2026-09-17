"""
Console — rendre l'affichage sûr sous Windows.

POURQUOI : la console Windows de la machine du CDG est en cp1252. Tout `print`
contenant une flèche « → » ou une coche « ✓ » lève UnicodeEncodeError et INTERROMPT
le script. Or ces caractères sont partout dans les messages des tests de validation
(« ✓ test_par_mai_egale_dashboard ») et de deux moteurs : les garde-fous du projet
plantaient AVANT d'afficher leur verdict.

On bascule donc la sortie standard du processus en UTF-8. En dernier recours
(errors="replace"), un caractère non représentable devient « ? » au lieu de tuer
le programme : un affichage dégradé vaut mieux qu'un test qui ne rend pas son verdict.
"""
from __future__ import annotations
import sys


def activer_utf8() -> None:
    """Passe stdout/stderr en UTF-8 tolérant. Idempotent, sans effet si déjà bon."""
    for flux in (sys.stdout, sys.stderr):
        reconfigurer = getattr(flux, "reconfigure", None)
        if reconfigurer is None:          # flux redirigé/remplacé : rien à faire
            continue
        try:
            reconfigurer(encoding="utf-8", errors="replace")
        except (ValueError, OSError):     # flux fermé ou non reconfigurable
            pass
