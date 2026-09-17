"""Socle de données MICROPOP (schéma, historisation, calendrier, paramètres).

Au chargement du socle, on sécurise l'affichage console (cp1252 sous Windows) :
voir socle/console.py. Tout le projet passe par le socle, donc ce seul point
d'entrée suffit à protéger moteurs, imports, tests et API.
"""
from .console import activer_utf8 as _activer_utf8

_activer_utf8()
