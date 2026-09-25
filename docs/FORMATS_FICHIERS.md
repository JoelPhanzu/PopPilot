# Formats des fichiers mensuels à fournir à PopPilot

Règle commune : **ligne 1 = en-têtes**, une ligne par élément, pas de cellules fusionnées.
Montants en nombres (la virgule décimale est acceptée). Les noms d'agence, de superviseur et
d'agent doivent être **écrits exactement comme dans l'extraction crédit du CBS**.

---

## 1. Roster + objectifs (fichier OBJECTIF) — page Import, domaine « objectifs »
Feuille nommée **OBJECTIF** (sinon la première). Date d'effet = **1er du mois** concerné (il ne
vaut que pour ce mois). Les colonnes sont repérées par leur **EN-TÊTE** : les deux formats
ci-dessous sont acceptés, dans cet ordre ou non.

Format courant (7 colonnes, exemple du CDG) :

| En-tête | Contenu | Exemple |
|---|---|---|
| AGENCE | nom CBS de l'agence | AGENCE OZONE |
| SUPERVISEUR | nom du superviseur (nom court accepté, voir ci-dessous) | KANDA RODDY |
| AGENT DE CREDIT | nom de l'agent | SABWA TSHIBANGU PATRICK |
| #NOMBRE A DECAISSE | objectif en nombre de crédits | 10 |
| VOLUME | objectif de décaissement (USD) | 70 000 |
| PORTEFEUILLE | objectif d'encours (USD) | 250 000 |
| PAR | objectif de PAR : « 5% », 5 ou 0,05 | 5% |

Format long (8 colonnes) : PORTEFEUILLE est alors dédoublé en « PORTEFEUILLE (volume Encours) »
et « PORTEFEUILLE (Nombre de client) ». Une cellule vide = pas d'objectif (l'agent reste au roster).

**Noms** : un nom du fichier est rattaché au nom CBS s'il est identique, ou si **tous ses mots**
figurent dans le nom CBS de la **même agence** et qu'**un seul** nom CBS convient (casse, ordre
et espaces ignorés) : « KANDA RODDY » = « MBOLELA KANDA  RODDY ». Sinon (orthographe
différente, deux candidats), le portefeuille reste orphelin — PopPilot ne devine pas.
Cas relevés sur mai à corriger dans le fichier : « DAVID CIZA » (CBS : CHIZA CHIRIMULUME DAVID),
« STAFF RICHET » (CBS : MAZU MANGIEKUN Richet).
Superviseur MUTÉ : POMBO BIBISOMBE Arlette est à Gombe (roster correct), mais le CBS lui attribue
encore 129 crédits d'Ozone (468 k USD). Tant qu'ils ne sont pas réaffectés dans le CBS, ils
apparaissent en « portefeuille orphelin » d'Ozone : c'est voulu, ils n'ont plus de superviseur sur place.
**Complétude** : tout agent actif absent du fichier passe en « portefeuille orphelin ». Inclure
tous les agents actifs, même sans objectif. Les agences FERMÉES ou SUSPENDUES (Goma) sont un
« portefeuille gelé », jamais orphelin, et restent dans l'encours.

## 2. Taux de change journaliers — page Import, domaine « taux_change »
Première feuille, deux colonnes : **Date | Taux** (USD→CDF), un taux par jour.
Une date déjà en base avec un autre taux bloque l'import (elle sert au FINA/AML) : écrire
« oui » dans « Remplacer » pour l'écraser volontairement.

## 3. Crédits remboursés — page Import, domaine « remboursements »
Export CBS tel quel (feuille Worksheet, 9 colonnes : Date | N° échéance | N° client | Noms |
N° dossier | Montant déboursé | Capital | Intérêts | Pénalités). Importer d'abord l'encours
du même arrêté. Sert la productivité (pas les primes).

## 4. Compte de résultat par agence — page Import, domaine « compte_resultat_agence »
Fichier COMPTE_RESULTAT_<mois>_isolé.xlsx, feuille **Feuil2** : A = poste, B→G = Victoire,
Ozone, Goma, Lubumbashi, Masina, Gombe, H = MICROPOP. Refusé si MICROPOP ≠ somme des agences.

## 5. Recouvrement — page Primes
**Équipe | Agent | Agence | Montant 91-180 | Montant 181+ | Montant Radié**, puis une ligne
TOTAL (contrôle : la somme des agents doit la redonner).

## 6. Épargne des superviseurs — page Primes
**Agence | Cible | Réalisation | %**, puis une ligne TOTAL (contrôle). Le % est recalculé.
Le **mois** de la collecte est obligatoire (champ « Mois de la collecte ») : le fichier est
conservé à ce mois (table fait_collecte_epargne) ; ré-importer le même mois le remplace.
Prime : palier sur la réalisation **totale** (≥ 50 000 → 60 ; ≥ 70 000 → 100 ; ≥ 100 000 → 200 USD).

## 7. Historiques d'indicateurs — page Archives, onglet Séries
**Indicateur | Date | Agence | Valeur | Unité** (Agence vide = consolidé MICROPOP).
Indicateurs reconnus : encours_credit, par1, par30, par90, pct_par30, nb_credits, provisions,
epargne (tout autre nom est accepté comme nouvelle série).
