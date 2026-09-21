"""
Import budget + mapping dynamique compte→ligne budgétaire — CLAUDE.md §46-50, §61.
Le mapping est stocké dans la table mapping_budget (ÉDITABLE) : charges ET produits.
"""
from __future__ import annotations
import datetime as dt
import unicodedata
import openpyxl
from sqlalchemy import select
from socle.schema import FaitBudget, MappingBudget, get_session, init_db


def _f(v):
    if v in (None, ""): return 0.0
    try: return float(str(v).replace(",", ".").replace("\xa0", "").replace(" ", ""))
    except (ValueError, TypeError): return 0.0


def importer_budget(path, exercice=2026, hypothese="H1",
                    feuille="CHARGES ET PRODUITS CONSOLIDE", db_path="socle/micropop.db"):
    """Importe le budget MOIS PAR MOIS (non linéaire) depuis la feuille CONSOLIDE du fichier budget.
    Les 12 mois sont en colonnes 2-7 (janv-juin) puis 9-14 (juil-déc) ; col 8 et 15 = sous-totaux (ignorés)."""
    init_db(db_path)
    s = get_session(db_path)
    s.query(FaitBudget).filter(FaitBudget.exercice == exercice,
                               FaitBudget.hypothese == hypothese).delete()
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb[feuille] if feuille in wb.sheetnames else wb.worksheets[0]
    # colonnes des 12 mois (1-based) : janv..juin = 2..7, juil..déc = 9..14
    COLS_MOIS = {1: 2, 2: 3, 3: 4, 4: 5, 5: 6, 6: 7,
                 7: 9, 8: 10, 9: 11, 10: 12, 11: 13, 12: 14}
    n = 0
    for row in ws.iter_rows(min_row=2, values_only=True):
        ligne = row[0]
        if not ligne or not str(ligne).strip():
            continue
        ligne = str(ligne).strip()
        for mois, col in COLS_MOIS.items():
            montant = _f(row[col - 1]) if len(row) >= col else 0.0
            if montant:
                s.add(FaitBudget(exercice=exercice, hypothese=hypothese,
                                 ligne_budgetaire=ligne, mois=mois,
                                 montant_budgete=montant, type="budget"))
                n += 1
    s.commit(); s.close()
    return {"lignes_importees": n}


def importer_mapping(path, feuille, sens, date_effet=None, db_path="socle/micropop.db"):
    """Charge le mapping compte→ligne depuis une feuille 'Résultat *' dans mapping_budget.

    sens = 'charge' ou 'produit'. Remplace le mapping existant du même sens+date.

    REND COMPTE DE CE QU'IL ÉCARTE, et c'est le cœur de cette fonction. Deux
    rejets n'ont rien à voir l'un avec l'autre :

      - une ligne ENTIÈREMENT VIDE est du remplissage de tableur (un classeur
        s'étend souvent sur des centaines de lignes blanches). On l'ignore, et
        la signaler noierait le reste ;
      - une ligne qui porte QUELQUE CHOSE mais à qui il manque le numéro de
        compte ou la ligne budgétaire est un TROU DANS LE MAPPING. Le compte
        concerné ne sera rattaché à rien, son réalisé disparaîtra du suivi, et
        personne ne le saura. Celle-là se nomme.

    Les doublons de compte se nomment aussi : la dernière occurrence l'emporte
    en lecture, donc un compte listé deux fois avec deux lignes différentes
    change de rattachement sans prévenir.
    """
    init_db(db_path)
    s = get_session(db_path)
    if date_effet is None:
        date_effet = dt.date(2026, 1, 1)
    s.query(MappingBudget).filter(MappingBudget.sens == sens,
                                  MappingBudget.date_effet == date_effet).delete()
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb[feuille]

    n = 0
    vides = 0
    incompletes: list[dict] = []
    doublons: list[str] = []
    vus: set[str] = set()

    for numero_ligne, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        cellules = list(row) + [None] * (3 - len(row))
        compte = str(cellules[0] or "").strip()
        nom = str(cellules[1] or "").strip()
        ligne = str(cellules[2] or "").strip()

        if not (compte or nom or ligne):
            vides += 1                      # remplissage de tableur : sans intérêt
            continue

        if not compte or not compte[0].isdigit():
            incompletes.append({"feuille": feuille, "ligne_fichier": numero_ligne,
                                "manque": "numéro de compte (colonne A)",
                                "contenu": (nom or ligne)[:60]})
            continue
        if not ligne:
            incompletes.append({"feuille": feuille, "ligne_fichier": numero_ligne,
                                "manque": "ligne budgétaire (colonne C)",
                                "contenu": f"{compte} — {nom}"[:60]})
            continue

        if compte in vus:
            doublons.append(compte)
        vus.add(compte)

        s.add(MappingBudget(numero_compte=compte, ligne_budgetaire=ligne,
                            sens=sens, date_effet=date_effet))
        n += 1

    s.commit(); s.close()
    return {"sens": sens, "feuille": feuille, "comptes": n,
            "lignes_vides_ignorees": vides,
            "incompletes": incompletes, "doublons": sorted(set(doublons))}


def affecter_compte(numero_compte, ligne_budgetaire, sens, date_effet=None,
                    db_path="socle/micropop.db"):
    """Ajoute ou réaffecte un compte à une ligne budgétaire (édition dynamique)."""
    init_db(db_path)
    s = get_session(db_path)
    if date_effet is None:
        date_effet = dt.date.today()
    existant = s.execute(
        select(MappingBudget).where(MappingBudget.numero_compte == numero_compte,
                                    MappingBudget.date_effet == date_effet)
    ).scalar_one_or_none()
    if existant:
        existant.ligne_budgetaire = ligne_budgetaire
        existant.sens = sens
    else:
        s.add(MappingBudget(numero_compte=numero_compte, ligne_budgetaire=ligne_budgetaire,
                            sens=sens, date_effet=date_effet))
    s.commit(); s.close()
    return {"compte": numero_compte, "ligne": ligne_budgetaire, "sens": sens}


def lire_mapping(sens=None, db_path="socle/micropop.db"):
    """Renvoie {compte: (ligne, sens)} — dernière date d'effet par compte.

    DOCTRINE (tranchée avec le CDG) : le mapping est une donnée TRANSVERSALE.
    Le dernier chargé s'applique à TOUS les mois, y compris aux arrêtés
    antérieurs. Il ne se recharge pas à chaque suivi : les réaffectations de
    comptes sont rares, et lier un mapping à chaque date de rapport ferait
    ressaisir tous les mois une correspondance qui n'a pas bougé.

    Ce n'est pas qu'une commodité, c'est une NÉCESSITÉ DE CALCUL. Le réalisé
    mensuel vaut cumul(N) − cumul(N−1). Si ces deux cumuls étaient mappés
    différemment — parce qu'une réaffectation serait intervenue entre les deux —
    leur différence ne voudrait plus rien dire : on soustrairait deux
    regroupements de comptes distincts. Un mapping daté par rapport casserait
    donc exactement l'indicateur que le suivi budgétaire produit.

    CE QU'ON PERD, et il faut le savoir : après une réaffectation, rejouer un
    mois déjà publié ne redonne pas les chiffres publiés à l'époque, puisqu'il
    est recalculé avec le mapping du jour. `date_effet` reste stocké pour garder
    la TRACE de chaque version (qui a changé quoi, quand) — mais il ne filtre
    pas la lecture. Si un jour la BCC exigeait de rejouer une déclaration à
    l'identique, c'est ce filtre qu'il faudrait ajouter, et il faudrait alors
    figer le mapping pour tout un exercice, jamais en cours d'année.
    """
    s = get_session(db_path)
    q = select(MappingBudget).order_by(MappingBudget.date_effet)
    if sens:
        q = q.where(MappingBudget.sens == sens)
    rows = s.execute(q).scalars().all()
    s.close()
    mapping = {}
    for r in rows:   # dernière date d'effet gagne (ordre croissant)
        mapping[r.numero_compte] = (r.ligne_budgetaire, r.sens)
    return mapping


def _normaliser(nom) -> str:
    """Minuscules, sans accents, espaces normalisés — pour comparer des noms d'onglets."""
    nom = unicodedata.normalize("NFKD", str(nom))
    nom = "".join(c for c in nom if not unicodedata.combining(c))
    return " ".join(nom.lower().split())


#  Mots-clés par sens. Une feuille est reconnue si son nom les contient TOUS.
#  On raisonne sur des racines (« charge », « produit ») et non sur un libellé
#  exact : les onglets sont nommés à la main et varient d'un classeur à l'autre —
#  « Résultat Produit », « Résultat produits », « RESULTAT DES CHARGES 2026 »
#  désignent tous la même chose. Exiger un libellé au caractère près obligerait
#  le CDG à renommer son classeur pour satisfaire l'outil, ce qui est l'inverse
#  du service rendu.
MOTS_CLES_FEUILLE = {
    "charge": ("resultat", "charge"),
    "produit": ("resultat", "produit"),
}


def _trouver_feuille(wb, souhaitee: str | None, sens: str | None = None):
    """Retrouve l'onglet voulu : nom exact d'abord, mots-clés ensuite.

    Si `souhaitee` est fourni explicitement (paramètre d'import), il prime et
    doit correspondre — on ne devine pas à la place de quelqu'un qui a désigné
    une feuille. Sinon on reconnaît par mots-clés, insensible à la casse, aux
    accents, au singulier/pluriel et aux mots en plus.
    """
    if souhaitee:
        voulue = _normaliser(souhaitee)
        for nom in wb.sheetnames:
            if _normaliser(nom) == voulue:
                return nom
        return None

    racines = MOTS_CLES_FEUILLE[sens]
    candidates = [nom for nom in wb.sheetnames
                  if all(r in _normaliser(nom) for r in racines)]
    #  Plusieurs candidates (« Résultat charges » et « Résultat charges N-1 ») :
    #  la plus courte est la principale, les variantes ajoutent des mots.
    return min(candidates, key=lambda n: len(_normaliser(n))) if candidates else None


#  Contrat de format, énoncé à un seul endroit et cité dans tous les messages
#  d'erreur : quelqu'un qui se trompe de fichier doit lire ce qu'on attend,
#  pas seulement qu'on a refusé.
FORMAT_MAPPING = (
    "Format attendu, IDENTIQUE dans les deux feuilles : ligne 1 = en-têtes "
    "(ignorée), colonne A = numéro de compte comptable (doit commencer par un "
    "chiffre), colonne C = libellé de la ligne budgétaire. La colonne B est "
    "libre (elle sert en général au libellé du compte). Les lignes dont la "
    "colonne A ou C est vide sont ignorées."
)


def _apercu_feuille(ws, lignes=3) -> str:
    """Les premières lignes d'une feuille, pour DIRE ce qu'on y a lu."""
    vues = []
    for i, row in enumerate(ws.iter_rows(min_row=1, max_row=lignes, values_only=True)):
        cellules = [("" if v is None else str(v))[:28] for v in (row or ())[:4]]
        vues.append(f"L{i + 1} : " + " | ".join(c or "(vide)" for c in cellules))
    return " ; ".join(vues) if vues else "feuille vide"


def importer_mapping_budget(path, feuille_charges=None, feuille_produits=None,
                            date_effet=None, db_path="socle/micropop.db"):
    """Charge le mapping compte→ligne budgétaire depuis le FICHIER DE SUIVI BUDGÉTAIRE.

    Les deux feuilles en un seul passage : « Résultat charges » et « Résultat
    produits ». C'est la source désignée par le CDG — et non le mapping du
    fichier magique (Etats financiers), qui sert au BILAN et n'a ni le même
    découpage ni la même finalité. Confondre les deux mettrait des lignes de
    bilan dans un suivi budgétaire.

    Sans ce mapping, `engine/budget.py` ne peut rattacher AUCUN compte de la
    balance à une ligne budgétaire : le réalisé vaut alors 0,00 sur toutes les
    lignes, en face d'un budget bien chargé. C'est précisément le symptôme
    observé en production, et la raison pour laquelle ce mapping doit être
    importable depuis la plateforme au lieu de n'exister qu'en ligne de commande.
    """
    if date_effet is None:
        date_effet = dt.date(dt.date.today().year, 1, 1)
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)

    demandees = {"charge": feuille_charges, "produit": feuille_produits}
    trouvees = {sens: _trouver_feuille(wb, nom, sens)
                for sens, nom in demandees.items()}
    manquantes = [s for s, f in trouvees.items() if f is None]
    if manquantes:
        quoi = " et ".join(
            (f"« {demandees[s]} »" if demandees[s]
             else f"une feuille dont le nom contient « résultat » et « {s} »")
            for s in manquantes)
        raise ValueError(
            f"Feuille(s) introuvable(s) : {quoi}. "
            f"Le fichier contient : {', '.join(wb.sheetnames)}. "
            f"Le classeur doit porter DEUX feuilles, une par sens — la casse, les "
            f"accents, le singulier/pluriel et les mots en plus n'ont pas "
            f"d'importance (« Résultat Produit » convient). {FORMAT_MAPPING}")

    resultat = {"date_effet": date_effet, "par_sens": {}, "comptes": 0,
                "incompletes": [], "doublons": [], "lignes_vides_ignorees": 0}
    for sens, feuille in trouvees.items():
        r = importer_mapping(path, feuille, sens, date_effet=date_effet, db_path=db_path)
        resultat["par_sens"][sens] = {"feuille": feuille, "comptes": r["comptes"]}
        resultat["comptes"] += r["comptes"]
        resultat["incompletes"].extend(r["incompletes"])
        resultat["doublons"].extend(r["doublons"])
        resultat["lignes_vides_ignorees"] += r["lignes_vides_ignorees"]

    #  Un résumé lisible sans dépiler la liste : c'est lui qui s'affiche à l'écran.
    resultat["a_completer"] = len(resultat["incompletes"])
    if resultat["incompletes"]:
        resultat["avertissement"] = (
            f"{len(resultat['incompletes'])} ligne(s) du fichier n'ont PAS été "
            f"chargées faute d'un numéro de compte ou d'une ligne budgétaire. "
            f"Les comptes concernés ne seront rattachés à aucune ligne : leur "
            f"réalisé n'apparaîtra nulle part dans le suivi budgétaire.")

    if resultat["comptes"] == 0:
        #  Les feuilles ont été trouvées mais n'ont rien donné : le problème est
        #  dans la DISPOSITION des colonnes. On montre ce qu'on y a lu, sinon
        #  l'opérateur n'a aucun moyen de savoir ce qui cloche.
        apercus = " // ".join(
            f"[{trouvees[s]}] {_apercu_feuille(wb[trouvees[s]])}" for s in trouvees)
        raise ValueError(
            f"Les deux feuilles ont bien été trouvées, mais aucun couple "
            f"compte→ligne n'a pu en être lu. {FORMAT_MAPPING} "
            f"Voici ce qui a été lu : {apercus}")
    return resultat


def supprimer_affectation(numero_compte, date_effet=None, db_path="socle/micropop.db"):
    """Retire l'affectation d'un compte (édition manuelle DAF / CDG)."""
    init_db(db_path)
    s = get_session(db_path)
    q = s.query(MappingBudget).filter(MappingBudget.numero_compte == numero_compte)
    if date_effet is not None:
        q = q.filter(MappingBudget.date_effet == date_effet)
    n = q.delete()
    s.commit()
    s.close()
    return {"compte": numero_compte, "supprimees": n}


def mapping_detaille(db_path="socle/micropop.db"):
    """Mapping en vigueur, mis à plat pour l'affichage et l'édition."""
    s = get_session(db_path)
    rows = s.execute(select(MappingBudget).order_by(
        MappingBudget.sens, MappingBudget.numero_compte, MappingBudget.date_effet)).scalars().all()
    s.close()
    # Dernière date d'effet gagnante par compte — même règle que lire_mapping,
    # pour que l'écran montre EXACTEMENT ce que le moteur applique.
    par_compte = {}
    for r in rows:
        par_compte[r.numero_compte] = {
            "numero_compte": r.numero_compte,
            "ligne_budgetaire": r.ligne_budgetaire,
            "sens": r.sens,
            "date_effet": r.date_effet,
        }
    return sorted(par_compte.values(), key=lambda m: (m["sens"] or "", m["numero_compte"]))


if __name__ == "__main__":
    import sys
    print(importer_budget(sys.argv[1]))
