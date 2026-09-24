# 📂 Améliorations PopPilot — dossier de référence (v2)

Dépose ce dossier dans ton projet. Tout est ADDITIF : rien de l'existant n'est écrasé.

## 👉 COMMENCE PAR : PLAN_IMPLEMENTATION.md
Il te dit exactement où déposer chaque fichier, quels SQL exécuter, et quel message donner
à Claude Code. C'est ton mode d'emploi.

## Contenu
- **PLAN_IMPLEMENTATION.md** — le mode d'emploi pas à pas (LIS-LE EN PREMIER).
- **INSTRUCTIONS_AMELIORATIONS.md** — le détail des 7 chantiers.
- **moteurs/** — moteurs testés à copier dans api/engine/ :
   - moteur_filtres.py — filtres tableau de bord (agence, sexe, produit, durée, client, agent, superviseur)
   - eljo_smart.py — messagerie Eljo Smart (répond avec les vraies données, cloisonné)
   - traitement_sage.py — transforme le GL CBS → format SAGE (testé, équilibre à zéro)
   - import_compte_resultat_agence.py — compte de résultat par agence (testé)
   - interets_par_agent.py — intérêts encaissés par agent (testé)
- **06_ajout_tables_ameliorations.sql** + **07_ajout_tables_modules.sql** — nouvelles tables (additif).
- **exemples_donnees/** — vrais fichiers de référence.

## Les 3 nouvelles demandes couvertes
✓ Eljo Smart (messagerie qui répond avec les vraies données, jamais d'invention)
✓ Filtres enrichis (agence, sexe, produit, durée CT/MT/LT, client, agent, superviseur)
✓ Archives modifiables (remplaçables + éditables en ligne + séries temporelles pour les courbes)

## Principe
Plateforme évolutive : on empile les fonctionnalités, on ne reconstruit jamais.
Chaque brique est testée et s'ajoute sans perturber ce qui tourne.
