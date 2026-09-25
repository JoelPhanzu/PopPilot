"""
Eljo Smart — messagerie intelligente de PopPilot.
L'utilisateur pose une question sur ses données ; Eljo répond avec la VRAIE donnée,
calculée par les moteurs validés. JAMAIS de chiffre inventé (principe PopPilot).

Architecture (sûre et évolutive) :
  question (langage naturel)
     → analyse d'intention (quel indicateur ? quelle date ? quel périmètre ?)
     → appel du moteur validé correspondant (par, provisions, epargne, etc.)
     → réponse formulée + valeur exacte + source (traçabilité)

SÉCURITÉ : Eljo hérite du rôle et de l'agence de l'utilisateur (auth_supabase).
  Une AGENCE ne peut interroger QUE ses données — même mécanisme de cloisonnement que l'API.

ÉVOLUTIF : chaque nouvel indicateur = une nouvelle "intention" ajoutée au registre,
  sans toucher au reste. On commence par le crédit, on étend au fil de l'eau.

STRICTEMENT ADDITIF : module autonome, ne modifie aucun moteur existant.
"""
from __future__ import annotations
import datetime as dt
import re

# Registre d'intentions : mot-clé → (moteur, libellé). Extensible.
INTENTIONS = {
    # « par » seul n'est PAS un mot-clé : c'est la préposition (« encours par agence »).
    # Le PAR se reconnaît à sa MAJUSCULE (« PAR », « PAR30 ») ou à une formule sans ambiguïté
    # (« par30 », « portefeuille à risque », « retard ») — voir _parle_du_par.
    "par": {"mots": ["portefeuille à risque", "portefeuille a risque", "impayé", "impaye",
                     "retard"],
            "libelle": "PAR (portefeuille à risque)"},
    "encours": {"mots": ["encours", "portefeuille"], "libelle": "encours de crédit"},
    "provision": {"mots": ["provision", "dotation"], "libelle": "provisions"},
    "decaissement": {"mots": ["décaiss", "decaiss", "déboursé", "debourse", "octroi"],
                     "libelle": "décaissements"},
    "epargne": {"mots": ["épargne", "epargne", "dépôt", "depot"], "libelle": "épargne"},
    "resultat": {"mots": ["résultat", "resultat", "bénéfice", "benefice", "perte"],
                 "libelle": "résultat"},
}

MOIS = {"janvier": 1, "février": 2, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5,
        "juin": 6, "juillet": 7, "août": 8, "aout": 8, "septembre": 9, "octobre": 10,
        "novembre": 11, "décembre": 12, "decembre": 12}


def _parle_du_par(question: str) -> bool:
    """PAR = portefeuille à risque. Règle CDG : il s'écrit TOUJOURS en majuscules.
    « PAR », « PAR30 », « PAR 90 » (majuscules) ou « par30 » / « par 1 » (suivi d'un seuil)
    → PAR ; « par » minuscule seul → préposition."""
    return bool(re.search(r"\bPAR\s?(1|30|90)?\b", question)
                or re.search(r"\bpar\s?(1|30|90)\b", question, re.IGNORECASE))


def _contient(q: str, mot: str) -> bool:
    """Mot-clé en DÉBUT de mot (« décaiss » couvre « décaissement ») : « mai » ne se
    retrouve plus dans « maison », ni « perte » dans « experte »."""
    return re.search(r"(?<!\w)" + re.escape(mot), q) is not None


def analyser_question(question: str) -> dict:
    """Extrait l'intention, la date et le périmètre d'une question en langage naturel."""
    q = question.lower()
    intention = "par" if _parle_du_par(question) else None
    for cle, conf in INTENTIONS.items():
        if intention:
            break
        if any(_contient(q, m) for m in conf["mots"]):
            intention = cle
    # date : mois + année
    date = None
    for nom, num in MOIS.items():
        if re.search(rf"\b{nom}\b", q):
            an = re.search(r"20\d{2}", q)
            annee = int(an.group()) if an else dt.date.today().year
            date = (annee, num)
            break
    # périmètre agence
    agence = None
    for a in ["victoire", "ozone", "goma", "lubumbashi", "masina", "gombe"]:
        if a in q:
            agence = a.upper()
            break
    return {"intention": intention, "date": date, "agence_demandee": agence,
            "question": question}


def repondre(question: str, user: dict, resoudre_valeur) -> dict:
    """Construit la réponse. resoudre_valeur(intention, date, agence, user) est une fonction
    fournie par l'API qui appelle le VRAI moteur et renvoie la valeur (en respectant le rôle).
    Eljo ne calcule rien lui-même : il oriente et met en forme."""
    a = analyser_question(question)
    if not a["intention"]:
        return {"reponse": "Je n'ai pas identifié l'indicateur demandé. "
                "Essayez : « PAR de mai à Ozone », « encours de juin », « résultat de juillet ».",
                "valeur": None, "comprehension": a}
    # cloisonnement : une AGENCE ne peut demander qu'à sa propre agence
    if user["role"] == "AGENCE":
        if a["agence_demandee"] and a["agence_demandee"] not in (user["agence"] or "").upper():
            return {"reponse": f"Vous êtes habilité(e) uniquement pour {user['agence']}. "
                    "Je ne peux pas répondre pour une autre agence.", "valeur": None}
        a["agence_demandee"] = user["agence"]
    # déléguer le calcul au vrai moteur (via l'API), qui renvoie la valeur exacte
    try:
        valeur, detail = resoudre_valeur(a["intention"], a["date"], a["agence_demandee"], user)
    except Exception as e:
        return {"reponse": f"Donnée indisponible : {e}. "
                "Vérifiez que l'arrêté est importé.", "valeur": None, "comprehension": a}
    lib = INTENTIONS[a["intention"]]["libelle"]
    portee = f" pour {a['agence_demandee']}" if a["agence_demandee"] else ""
    return {"reponse": f"Le {lib}{portee} est de {valeur:,.2f}." if isinstance(valeur, (int, float))
            else f"{lib}{portee} : {valeur}",
            "valeur": valeur, "detail": detail, "comprehension": a,
            "source": "moteurs PopPilot validés"}


if __name__ == "__main__":
    # démo d'analyse (sans base)
    for q in ["Quel est le PAR de mai à Ozone ?", "encours de juin",
              "résultat de juillet à Goma", "bonjour"]:
        print(q, "→", analyser_question(q))
