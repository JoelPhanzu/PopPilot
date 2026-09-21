"""
Référentiel des états financiers — bilan et compte de résultat, ligne à ligne.

TRANSCRIT DU FICHIER MAGIQUE (feuilles BILAN et « Compte de résultat »), codes
BCC compris : V1.F0a.xx (actif), V1.F0p.xx (passif), V1.F1.xx (résultat).
Il n'y a ici AUCUN choix de présentation : l'ordre des lignes, leurs libellés,
les sous-totaux et jusqu'aux lignes qui valent zéro sont ceux du référentiel.
Une ligne à zéro se publie — l'absence d'une ligne attendue par la BCC est une
anomalie de déclaration, pas une économie de place.

POURQUOI CE MODULE EXISTE : `engine/etats_financiers.py` agrège la balance en
QUATRE rubriques par côté (Immobilisations, Opérations clientèle, Opérations
diverses, Trésorerie). C'est juste — l'écart au fichier magique est nul — mais
c'est un RÉSUMÉ : on n'y lit ni « (39) Créances litigieuses », ni le détail des
comptes qui composent chaque ligne. Ce module rend le détail sans toucher à
l'agrégat, qui reste la référence validée.

SIGNES — la seule subtilité, et elle est mécanique :
  `solde_net` = Débit − Crédit (positif = débiteur).
  Chaque ligne porte donc deux signes distincts, qu'il ne faut pas confondre :
    - `orientation` : ce par quoi multiplier la somme des soldes pour obtenir
      le montant tel que le référentiel l'AFFICHE (toujours positif en
      exploitation normale). Un compte de passif est créditeur (solde négatif),
      son orientation vaut donc −1.
    - `signe` : la façon dont la ligne entre dans SON SOUS-TOTAL. Les provisions
      pour dépréciation (38, 48, 58) et les amortissements (28) s'affichent en
      positif mais se DÉDUISENT — c'est exactement ce que fait le fichier
      magique, et le sous-total ne boucle pas autrement.

Vérifié au centime contre ETATS_FINANCIERS_USD_MAI_2026.xlsx : les quatre
sous-totaux de l'actif, les quatre du passif, le total général des deux côtés,
et les six soldes intermédiaires du compte de résultat (80, 82, 83, 84, 85, 87).
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Ligne:
    """Une ligne élémentaire : elle lit des préfixes de comptes dans la balance."""
    code: str
    libelle: str
    prefixes: tuple[str, ...]
    orientation: int = 1        # +1 débiteur (actif, charge), −1 créditeur (passif, produit)
    signe: int = 1              # contribution au sous-total : +1 ajoute, −1 déduit
    #  Préfixe partagé actif/passif (37, 40, 42…) : la ligne ne prend que la
    #  part de son côté, le solde global décidant du côté (règle du moteur).
    mixte: bool = False


@dataclass(frozen=True)
class SousTotal:
    """Une ligne de sous-total : elle ne lit rien, elle somme des codes."""
    code: str
    libelle: str
    composants: tuple[str, ...] = field(default_factory=tuple)
    #  Un sous-total de sous-totaux (TOTAL GENERAL) : même mécanique.
    total_general: bool = False


# ─────────────────────────────────────────────────────────────────────────────
# ACTIF — V1.F0a
# ─────────────────────────────────────────────────────────────────────────────
ACTIF: list[Ligne | SousTotal] = [
    SousTotal("V1.F0a.01", "TOTAL GENERAL",
              ("V1.F0a.02", "V1.F0a.08", "V1.F0a.15", "V1.F0a.24"), total_general=True),

    SousTotal("V1.F0a.02", "Opérations de trésorerie (S/Total)",
              ("V1.F0a.03", "V1.F0a.04", "V1.F0a.05", "V1.F0a.06", "V1.F0a.07")),
    Ligne("V1.F0a.03", "(57)  Caisse", ("57",)),
    Ligne("V1.F0a.04", "(56)  Banque, organe faîtier et autres I. F.", ("56",), mixte=True),
    Ligne("V1.F0a.05", "(53)  Prêts à terme (auprès de l'organe faîtier ou autres I.F.)",
          ("53",), mixte=True),
    Ligne("V1.F0a.06", "(52)  Titre à court terme", ("52",)),
    Ligne("V1.F0a.07", "(58)  Provisions pour dépréciation des comptes de la classe 5",
          ("58",), orientation=-1, signe=-1),

    SousTotal("V1.F0a.08", "Opérations avec la clientèle (S/Total)",
              ("V1.F0a.09", "V1.F0a.10", "V1.F0a.11", "V1.F0a.12", "V1.F0a.13", "V1.F0a.14")),
    Ligne("V1.F0a.09", "(32)  Crédit à court terme", ("32",)),
    Ligne("V1.F0a.10", "(31)  Crédit à moyen terme", ("31",)),
    Ligne("V1.F0a.11", "(30)  Crédit à long terme", ("30",)),
    Ligne("V1.F0a.12", "(37)  Suspens de la clientèle ou des membres", ("37",), mixte=True),
    Ligne("V1.F0a.13", "(38)  Provisions pour dépréciation des comptes de la classe 3",
          ("38",), orientation=-1, signe=-1),
    Ligne("V1.F0a.14", "(39)  Créances litigieuses ou en retard (balance âgée)", ("39",)),

    SousTotal("V1.F0a.15", "Opérations diverses (S/Total)",
              ("V1.F0a.16", "V1.F0a.17", "V1.F0a.18", "V1.F0a.19", "V1.F0a.20",
               "V1.F0a.21", "V1.F0a.22", "V1.F0a.23")),
    Ligne("V1.F0a.16", "(40)  Fournisseur", ("40",), mixte=True),
    Ligne("V1.F0a.17", "(42)  Personnel", ("42",), mixte=True),
    Ligne("V1.F0a.18", "(43)  Etat", ("43",), mixte=True),
    Ligne("V1.F0a.19", "(44)  Actionnaires et Associés", ("44",), mixte=True),
    Ligne("V1.F0a.20", "(45)  Compte de liaison", ("45",), mixte=True),
    Ligne("V1.F0a.21", "(46)  Débiteurs divers", ("46",), mixte=True),
    Ligne("V1.F0a.22", "(47)  Régularisations et emplois divers", ("47",), mixte=True),
    Ligne("V1.F0a.23", "(48)  Provisions pour dépréciation des comptes de la classe 4",
          ("48",), orientation=-1, signe=-1),

    SousTotal("V1.F0a.24", "Immobilisations (S/Total)",
              ("V1.F0a.25", "V1.F0a.26", "V1.F0a.27", "V1.F0a.28", "V1.F0a.29",
               "V1.F0a.30", "V1.F0a.31", "V1.F0a.32")),
    Ligne("V1.F0a.25", "(20)  Valeurs incorporelles immobilisées", ("20",)),
    Ligne("V1.F0a.26", "(22)  Autres immobilisations corporelles", ("22",)),
    Ligne("V1.F0a.27", "(23)  Immobilisations corporelles en cours", ("23",)),
    Ligne("V1.F0a.28", "(24)  Avances et acomptes sur commandes d'immob.", ("24",)),
    Ligne("V1.F0a.29", "(25)  Titres de participation et autres val. engagées à + 1an", ("25",)),
    Ligne("V1.F0a.30", "(26)  Prêts et titres à souscription obligatoire", ("26",)),
    Ligne("V1.F0a.31", "(27)  Garanties et cautionnements à moyen et long termes", ("27",)),
    Ligne("V1.F0a.32",
          "(28)  Amortissements et Provisions pour dépréciation des comptes de la classe 2",
          ("28",), orientation=-1, signe=-1),
]

# ─────────────────────────────────────────────────────────────────────────────
# PASSIF — V1.F0p
# ─────────────────────────────────────────────────────────────────────────────
PASSIF: list[Ligne | SousTotal] = [
    SousTotal("V1.F0p.01", "TOTAL GENERAL",
              ("V1.F0p.02", "V1.F0p.05", "V1.F0p.11", "V1.F0p.23"), total_general=True),

    SousTotal("V1.F0p.02", "Opérations de trésorerie (S/Total)",
              ("V1.F0p.03", "V1.F0p.04")),
    Ligne("V1.F0p.03", "(56)  Banque, organe faîtier et autres I. F.",
          ("56",), orientation=-1, mixte=True),
    Ligne("V1.F0p.04", "(53)  Emprunts à terme (organe faîtier ou autres I.F)",
          ("53",), orientation=-1, mixte=True),

    SousTotal("V1.F0p.05", "Opérations avec la clientèle (S/Total)",
              ("V1.F0p.06", "V1.F0p.07", "V1.F0p.08", "V1.F0p.09", "V1.F0p.10")),
    Ligne("V1.F0p.06", "(33)  Epargnes et dépôts ordinaires", ("33",), orientation=-1),
    Ligne("V1.F0p.07", "(34)  Dépôts à terme", ("34",), orientation=-1),
    Ligne("V1.F0p.08", "(35)  Dépôts à régime spécial", ("35",), orientation=-1),
    Ligne("V1.F0p.09", "(36)  Autres comptes de la clientèle ou de membres",
          ("36",), orientation=-1),
    Ligne("V1.F0p.10", "(37)  Suspens de la clientèle ou des membres",
          ("37",), orientation=-1, mixte=True),

    SousTotal("V1.F0p.11", "Opérations diverses (S/Total)",
              ("V1.F0p.12", "V1.F0p.13", "V1.F0p.14", "V1.F0p.15", "V1.F0p.16",
               "V1.F0p.17", "V1.F0p.18", "V1.F0p.19", "V1.F0p.20", "V1.F0p.21",
               "V1.F0p.22")),
    Ligne("V1.F0p.12", "(40)  Fournisseur", ("40",), orientation=-1, mixte=True),
    Ligne("V1.F0p.13", "(42)  Personnel", ("42",), orientation=-1, mixte=True),
    Ligne("V1.F0p.14", "(43)  Etat", ("43",), orientation=-1, mixte=True),
    Ligne("V1.F0p.15", "(44)  Actionnaires et Associés", ("44",), orientation=-1, mixte=True),
    Ligne("V1.F0p.16", "(45)  Compte de liaison", ("45",), orientation=-1, mixte=True),
    Ligne("V1.F0p.17", "(46)  Créditeurs divers", ("46",), orientation=-1, mixte=True),
    Ligne("V1.F0p.18", "(47)  Régularisations et emplois divers",
          ("47",), orientation=-1, mixte=True),
    Ligne("V1.F0p.19", "(15)  Subventions d'équipement", ("15",), orientation=-1),
    Ligne("V1.F0p.20", "(16)  Emprunts et dettes à M&L termes", ("16",), orientation=-1),
    Ligne("V1.F0p.21", "(17)  Fonds de financements et de garantie", ("17",), orientation=-1),
    Ligne("V1.F0p.22", "(18)  Provision pour risques, charges et pertes",
          ("18",), orientation=-1),

    SousTotal("V1.F0p.23", "Fonds propres (S/Total)",
              ("V1.F0p.24", "V1.F0p.25", "V1.F0p.26", "V1.F0p.27", "V1.F0p.28")),
    Ligne("V1.F0p.24", "(14)  Plus-values et provisions réglementées", ("14",), orientation=-1),
    #  (13) Résultat net : en cours d'année le compte 13 vaut 0 et le résultat de
    #  l'exercice n'est pas encore affecté. La ligne est alimentée par le RÉSULTAT
    #  CALCULÉ (classes 6 et 7), comme le fait le fichier magique — sans quoi le
    #  passif ne boucle pas. Traitement particulier dans `construire_bilan`.
    Ligne("V1.F0p.25", "(13)  Résultat net", ("13",), orientation=-1),
    Ligne("V1.F0p.26", "(12)  Report à nouveau", ("12",), orientation=-1),
    Ligne("V1.F0p.27", "(11)  Réserves et primes liées au capital", ("11",), orientation=-1),
    Ligne("V1.F0p.28", "(10)  Capital", ("10",), orientation=-1),
]

# Code de la ligne « Résultat net » du passif (alimentée par le calcul, pas par le compte 13).
CODE_RESULTAT_PASSIF = "V1.F0p.25"

# ─────────────────────────────────────────────────────────────────────────────
# COMPTE DE RÉSULTAT — V1.F1
# Les soldes intermédiaires (80, 82, 83, 84, 85, 87) sont des SousTotal : ils se
# calculent, ils ne se lisent pas dans la balance.
# ─────────────────────────────────────────────────────────────────────────────
RESULTAT: list[Ligne | SousTotal] = [
    Ligne("V1.F1.01",
          "(70)  + Produits sur opérations avec l'organe faîtier et autres intermédiaires financiers",
          ("70",), orientation=-1),
    Ligne("V1.F1.02", "(71)  + Produits sur opérations avec la clientèle ou les membres",
          ("71",), orientation=-1),
    Ligne("V1.F1.03", "(72)  + Produits financiers divers", ("72",), orientation=-1),
    Ligne("V1.F1.04", "(73)  + Autres produits financiers", ("73",), orientation=-1),
    Ligne("V1.F1.05",
          "(60)  - charges sur opérations avec l'organe faîtier et autres intermédiaires financiers",
          ("60",), signe=-1),
    Ligne("V1.F1.06", "(61)  - Charges sur opérations avec la clientèle ou les membres",
          ("61",), signe=-1),
    Ligne("V1.F1.07", "(62)  - Charges financières diverses", ("62",), signe=-1),
    Ligne("V1.F1.08", "(63)  - Autres charges financières", ("63",), signe=-1),
    SousTotal("V1.F1.09", "(80)  Produit net financier",
              ("V1.F1.01", "V1.F1.02", "V1.F1.03", "V1.F1.04",
               "V1.F1.05", "V1.F1.06", "V1.F1.07", "V1.F1.08")),

    Ligne("V1.F1.10", "(74)  + Produits accessoires", ("74",), orientation=-1),
    Ligne("V1.F1.11", "(64)  - Charges générales d'exploitation", ("64",), signe=-1),
    Ligne("V1.F1.12", "(65)  - Charges du personnel", ("65",), signe=-1),
    Ligne("V1.F1.13", "(66)  - Impôts et taxes", ("66",), signe=-1),
    SousTotal("V1.F1.14", "(82)  Résultat brut d'exploitation",
              ("V1.F1.09", "V1.F1.10", "V1.F1.11", "V1.F1.12", "V1.F1.13")),

    Ligne("V1.F1.15", "(78)  + Reprises sur amortissements", ("78",), orientation=-1),
    Ligne("V1.F1.16",
          "(79)  + Reprises des provisions et récupération sur créances irrécouvrables",
          ("79",), orientation=-1),
    Ligne("V1.F1.17", "(68)  - Dotations aux amortissements", ("68",), signe=-1),
    Ligne("V1.F1.18",
          "(69)  - Dotations aux provisions et pertes sur créances irrécouvrables",
          ("69",), signe=-1),
    SousTotal("V1.F1.19", "(83)  Résultat courant d'exploitation",
              ("V1.F1.14", "V1.F1.15", "V1.F1.16", "V1.F1.17", "V1.F1.18")),

    Ligne("V1.F1.20", "(76)  + Subventions d'exploitation", ("76",), orientation=-1),
    Ligne("V1.F1.21", "(77)  + Produits exceptionnels", ("77",), orientation=-1),
    Ligne("V1.F1.22", "(67)  - Pertes exceptionnelles", ("67",), signe=-1),
    SousTotal("V1.F1.23", "(84)  Résultat exceptionnel",
              ("V1.F1.20", "V1.F1.21", "V1.F1.22")),

    SousTotal("V1.F1.24", "(85)  Résultat avant impôt", ("V1.F1.19", "V1.F1.23")),
    Ligne("V1.F1.25", "(86)  - Impot sur le résultat", ("86",), signe=-1),
    SousTotal("V1.F1.26", "(87)  Résultat net de l'exercice", ("V1.F1.24", "V1.F1.25")),
]


def prefixes_connus() -> set[str]:
    """Tous les préfixes que le référentiel sait placer, les trois états confondus.

    Sert à repérer ce que la balance contient et que le référentiel ignorerait :
    un compte non placé n'entre dans aucun total, et le déséquilibre qui s'ensuit
    doit être nommé, pas cherché.
    """
    connus: set[str] = set()
    for etat in (ACTIF, PASSIF, RESULTAT):
        for item in etat:
            if isinstance(item, Ligne):
                connus.update(item.prefixes)
    return connus
