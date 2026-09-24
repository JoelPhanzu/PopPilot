"""
Moteur de filtrage transversal (chantiers 1-2) — enrichissement des tableaux de bord.
Applique des filtres combinables sur fait_credit AVANT tout calcul de KPI.
Un seul filtre générique, réutilisé par tous les indicateurs (source unique).

STRICTEMENT ADDITIF : ne modifie aucun moteur existant. calculer_par, deriver_provisions,
etc. reçoivent la liste de prêts déjà filtrée.

Axes de filtrage :
  - agence, agent_credit, superviseur, sexe
  - produits (liste, multi-sélection)
  - client (numero_client)
  - duree : 'court' (<=12 mois OU groupe LISANGA), 'moyen' (>12 à 24), 'long' (>24)
"""
from __future__ import annotations


def filtrer_prets(prets, *, agence=None, agent=None, superviseur=None, sexe=None,
                  produits=None, client=None, duree=None):
    """Renvoie la sous-liste des prêts correspondant aux filtres fournis (None = pas de filtre)."""
    res = prets
    if agence:
        res = [p for p in res if (p.agence or "") == agence]
    if agent:
        res = [p for p in res if (p.agent_credit or "") == agent]
    if superviseur:
        res = [p for p in res if (p.superviseur or "") == superviseur]
    if sexe:
        res = [p for p in res if (p.sexe or "").upper() == sexe.upper()]
    if produits:
        setp = {x.strip().upper() for x in produits}
        res = [p for p in res if (p.produit_credit or "").strip().upper() in setp]
    if client:
        res = [p for p in res if (p.numero_client or "") == str(client)]
    if duree:
        res = [p for p in res if _classe_duree(p) == duree]
    return res


def _classe_duree(p) -> str:
    """Classe un prêt : court (<=12m ou groupe LISANGA), moyen (>12 à 24), long (>24)."""
    if getattr(p, "est_groupe", False):
        return "court"
    d = p.duree or 0
    if d <= 12:
        return "court"
    if d <= 24:
        return "moyen"
    return "long"


def valeurs_de_filtres(prets) -> dict:
    """Liste les valeurs disponibles pour peupler les menus déroulants de l'interface."""
    def uniques(attr):
        return sorted({getattr(p, attr) for p in prets if getattr(p, attr, None)})
    return {
        "agences": uniques("agence"),
        "agents": uniques("agent_credit"),
        "superviseurs": uniques("superviseur"),
        "produits": uniques("produit_credit"),
        "sexes": ["F", "H"],
        "durees": ["court", "moyen", "long"],
    }


if __name__ == "__main__":
    import datetime as dt, sys, os
    sys.path.insert(0, os.path.expanduser("~/mfi-pilotage"))
    try:
        from socle.schema import get_session, FaitCredit
        from sqlalchemy import select
        s = get_session(); prets = s.execute(select(FaitCredit).where(
            FaitCredit.date_arrete == dt.date(2026, 5, 30))).scalars().all(); s.close()
        print("Total prêts:", len(prets))
        v = valeurs_de_filtres(prets)
        print("Agences:", len(v["agences"]), "| Agents:", len(v["agents"]),
              "| Produits:", len(v["produits"]))
        # exemple : filtrer Ozone + court terme
        f = filtrer_prets(prets, agence="AGENCE OZONE", duree="court")
        print("Ozone court terme:", len(f), "prêts")
    except Exception as e:
        print("(démo nécessite la base :", e, ")")
