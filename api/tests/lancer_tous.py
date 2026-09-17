"""
Campagne de validation complète — lance toutes les suites et rend UN verdict global.

Usage :  python tests/lancer_tous.py

Le verdict distingue quatre états, jamais confondus :
  VALIDE      — les chiffres recalculés collent aux fichiers réels (écart nul).
  PARTIEL     — une partie seulement a été vérifiée : le reste n'a PAS été exécuté.
  NON VALIDE  — les sources ne sont pas là : rien n'a été vérifié (ce n'est PAS un succès).
  EN ECHEC    — un écart est apparu : ne livrer aucun chiffre tant qu'il n'est pas expliqué.

Le classement se fait sur le CODE DE SORTIE de chaque suite (donnees_test.lancer), jamais
sur une recherche de mot dans sa sortie. L'ancienne version cherchait « NON VALIDE » dans
le texte ; une suite PARTIELLE imprime « PARTIEL » et passait donc pour VALIDE, si bien que
la campagne annonçait « TOUT VALIDE » avec un cas jamais exécuté (l'écriture réelle du .xls
BCC). Un faux vert est pire que pas de test : c'est le seul défaut qui se propage à tout ce
qui s'appuie dessus.
"""
from __future__ import annotations

import os
import subprocess
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import donnees_test as D  # noqa: E402

SUITES = [
    ("test_socle.py",              "Phase 0 - socle"),
    ("test_securite_api.py",       "Securite API (cloisonnement agence)"),
    ("test_phase1_par.py",         "Phase 1 - credit"),
    ("test_phase2_compta.py",      "Phase 2 - comptabilite"),
    ("test_phase3_indicateurs.py", "Phase 3 - indicateurs"),
    ("test_epargne.py",            "Epargne"),
    ("test_fina.py",               "FINA - calcul"),
    ("test_fina_ecriture.py",      "FINA - ecriture .xls"),
    ("test_rapports_bcc.py",       "Rapports BCC (AML, systeme de paiement)"),
]


def main() -> int:
    print("=" * 72)
    print("PopPilot — campagne de validation")
    print(f"Sources reelles attendues dans : {D.dossier_donnees()}")
    print(f"  (dossier present : {os.path.isdir(D.dossier_donnees())})")
    print("=" * 72)

    verdicts: dict[str, str] = {}
    for fichier, titre in SUITES:
        print(f"\n--- {titre} ---")
        p = subprocess.run([sys.executable, os.path.join(ICI, fichier)],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", cwd=os.path.dirname(ICI))
        sortie = (p.stdout or "") + (p.stderr or "")
        print(sortie.rstrip())
        # Le code de sortie fait foi. « Traceback » reste surveillé pour le cas où une
        # suite planterait APRÈS avoir imprimé son verdict (code 0 mais sortie anormale).
        if "Traceback" in sortie:
            verdicts[titre] = "EN ECHEC"
        elif p.returncode == D.PARTIEL:
            verdicts[titre] = "PARTIEL (cas non verifies)"
        elif p.returncode == D.RIEN_VERIFIE:
            verdicts[titre] = "NON VALIDE (sources absentes)"
        elif p.returncode != D.VALIDE:
            verdicts[titre] = "EN ECHEC"
        else:
            verdicts[titre] = "VALIDE"

    print("\n" + "=" * 72)
    print("VERDICT")
    print("=" * 72)
    for titre, v in verdicts.items():
        print(f"  {v:32s} {titre}")

    if any(v == "EN ECHEC" for v in verdicts.values()):
        print("\n>>> ECHEC : un ecart est apparu. Ne livrer aucun chiffre avant explication.")
        return 1
    # PARTIEL et NON VALIDE interdisent tous les deux d'annoncer « tout validé » : dans
    # les deux cas, des cas n'ont pas ete executes. Seule la formulation change.
    incompletes = [t for t, v in verdicts.items()
                   if v.startswith("NON VALIDE") or v.startswith("PARTIEL")]
    if incompletes:
        print("\n>>> INCOMPLET : des cas n'ont PAS ete confrontes aux fichiers reels.")
        for t in incompletes:
            print(f"      - {t} : {verdicts[t]}")
        print(f"    Deposer les extractions dans {D.dossier_donnees()}")
        print("    ou definir POPPILOT_DONNEES vers le dossier qui les contient.")
        return 0
    print("\n>>> TOUT VALIDE : ecart nul contre les fichiers reels.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
