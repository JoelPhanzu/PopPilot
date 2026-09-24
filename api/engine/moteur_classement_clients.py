"""
Moteur de classement des clients (Top N meilleurs / pires) — enrichissement tableaux de bord.
Classe les clients selon un critère, AGRÉGÉ par client (tous ses crédits cumulés).

CRITÈRES (validés CDG) :
  STOCK (à une date de valorisation) :
    - encours : total encours crédit du client
    - par     : total encours en retard (PAR1) du client, + max jours de retard
    - epargne : solde d'épargne du client
    - fidelite: nombre de crédits + ancienneté (1re date de déboursement)
  FLUX (sur une période [début→fin]) :
    - decaissement : total déboursé par le client sur la période

Doctrine flux/stock respectée. Cloisonnement agence appliqué EN AMONT (l'API filtre les prêts
visibles avant d'appeler ce moteur). Se combine avec les filtres (agence, agent, produit...).
STRICTEMENT ADDITIF.
"""
from __future__ import annotations
import datetime as dt
from collections import defaultdict


def _agrege_clients_credit(prets):
    """Agrège les prêts par client : encours, retard, nb crédits, 1re date, nom, agence."""
    clients = defaultdict(lambda: {
        "numero_client": None, "nom_client": None, "agence": None, "agent": None,
        "encours": 0.0, "encours_retard": 0.0, "max_jours_retard": 0,
        "nb_credits": 0, "premiere_date": None, "total_debourse": 0.0})
    for p in prets:
        k = p.numero_client
        c = clients[k]
        c["numero_client"] = k
        c["nom_client"] = p.nom_client or c["nom_client"]
        c["agence"] = p.agence or c["agence"]
        c["agent"] = p.agent_credit or c["agent"]
        c["encours"] += p.encours or 0
        jr = p.jours_de_retard or 0
        if jr > 0:
            c["encours_retard"] += p.encours or 0
            c["max_jours_retard"] = max(c["max_jours_retard"], jr)
        c["nb_credits"] += 1
        c["total_debourse"] += p.montant_debourse or 0
        dd = p.date_deboursement
        if dd and (c["premiere_date"] is None or dd < c["premiere_date"]):
            c["premiere_date"] = dd
    return clients


def classer_clients(prets, critere="encours", top_n=10, sens="meilleurs",
                    date_debut=None, date_fin=None, epargne_par_client=None):
    """Renvoie le Top N clients selon le critère.
    - prets : extraction crédit à la date de valorisation (déjà filtrée/cloisonnée).
    - critere : encours | par | decaissement | epargne | fidelite
    - sens : 'meilleurs' ou 'pires' (le sens dépend du critère, voir ci-dessous).
    - date_debut/fin : requis pour 'decaissement' (flux).
    - epargne_par_client : dict {numero_client: solde} requis pour 'epargne'.
    """
    clients = _agrege_clients_credit(prets)

    # décaissement = flux → recalculer sur la période
    if critere == "decaissement":
        if not (date_debut and date_fin):
            raise ValueError("Le classement par décaissement exige une période [début, fin].")
        deb = defaultdict(float)
        noms = {}
        for p in prets:
            dd = p.date_deboursement
            if dd and date_debut <= dd <= date_fin:
                deb[p.numero_client] += p.montant_debourse or 0
                noms[p.numero_client] = p.nom_client
        items = [{"numero_client": k, "nom_client": noms.get(k),
                  "valeur": v, "critere": "décaissement (période)"} for k, v in deb.items()]

    elif critere == "epargne":
        epargne_par_client = epargne_par_client or {}
        items = [{"numero_client": k, "nom_client": c["nom_client"],
                  "valeur": epargne_par_client.get(k, 0.0), "critere": "épargne (solde)"}
                 for k, c in clients.items()]

    elif critere == "par":
        items = [{"numero_client": k, "nom_client": c["nom_client"], "agence": c["agence"],
                  "valeur": c["encours_retard"], "max_jours_retard": c["max_jours_retard"],
                  "encours": c["encours"], "critere": "PAR (encours en retard)"}
                 for k, c in clients.items()]

    elif critere == "fidelite":
        items = [{"numero_client": k, "nom_client": c["nom_client"],
                  "valeur": c["nb_credits"], "anciennete": c["premiere_date"],
                  "critere": "fidélité (nb crédits)"} for k, c in clients.items()]

    else:  # encours (défaut)
        items = [{"numero_client": k, "nom_client": c["nom_client"], "agence": c["agence"],
                  "valeur": c["encours"], "nb_credits": c["nb_credits"],
                  "critere": "encours"} for k, c in clients.items()]

    # tri : 'meilleurs' = valeur décroissante (sauf PAR où 'pires' = plus gros retard)
    # Pour PAR, 'meilleurs' clients = moins de retard ; 'pires' = plus de retard.
    reverse = (sens == "meilleurs")
    if critere == "par":
        # pires payeurs = plus gros encours en retard en tête
        reverse = (sens == "pires")
    items.sort(key=lambda x: x["valeur"], reverse=reverse)
    return items[:top_n]


if __name__ == "__main__":
    import sys, os
    sys.path.insert(0, os.path.expanduser("~/mfi-pilotage"))
    try:
        from socle.schema import get_session, FaitCredit
        from sqlalchemy import select
        s = get_session()
        prets = s.execute(select(FaitCredit).where(
            FaitCredit.date_arrete == dt.date(2026, 5, 30))).scalars().all()
        s.close()
        print("=== TOP 10 clients par ENCOURS ===")
        for i, c in enumerate(classer_clients(prets, "encours", 10, "meilleurs"), 1):
            print(f"  {i:2d}. {str(c['nom_client'])[:30]:30s} {c['valeur']:>12,.0f}  ({c['nb_credits']} crédits)")
        print("\n=== TOP 10 PIRES clients par PAR (retard) ===")
        for i, c in enumerate(classer_clients(prets, "par", 10, "pires"), 1):
            print(f"  {i:2d}. {str(c['nom_client'])[:30]:30s} retard {c['valeur']:>11,.0f}  ({c['max_jours_retard']}j)")
    except Exception as e:
        print("(démo nécessite la base :", e, ")")
