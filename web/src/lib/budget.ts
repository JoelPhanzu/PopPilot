/**
 * PopPilot — domaine BUDGET : ce que renvoie GET /budget.
 *
 * Les types suivent la sortie REELLE de `engine/budget.py` (suivi_budgetaire,
 * qui enveloppe analyse_ecart). Aucun ecart n'est recalcule ici.
 *
 * DEUX PIEGES, tous deux verifies par les tests de l'API :
 *
 *  1. Les `pct_*` du moteur sont des RAPPORTS, pas des pourcentages. Le moteur
 *     renvoie 1.25 la ou /par renvoie 10.99. Les passer tels quels a
 *     `pourcent()` afficherait « 1,25 % » pour un depassement de 25 %. D'ou
 *     `enPourcent()` ci-dessous, seul point de passage autorise.
 *
 *  2. Le REALISE MENSUEL est une difference de deux cumuls (la balance arrive
 *     cumulee depuis janvier). Quand la balance du mois precedent manque,
 *     l'API le declare — `niveau_mensuel_disponible: false` — et les montants
 *     mensuels ne veulent alors RIEN dire : ils valent le cumul entier. L'ecran
 *     doit refuser d'afficher ce niveau, pas l'afficher avec une note.
 */

export type SensLigne = "charge" | "produit" | string;

export type LigneBudget = {
  ligne: string;
  sens: SensLigne;
  /* Niveau MENSUEL : realise du mois vs budget du mois. */
  budget_mois: number;
  realise_mois: number;
  ecart_mois: number;
  /** Rapport, pas un pourcentage (1.25 = 125 %). */
  pct_realisation: number | null;
  /* Niveau CUMULE (a) : cumul depuis janvier vs budget ANNUEL total. */
  realise_cumule: number;
  budget_annuel: number;
  ecart_annuel: number;
  pct_progression: number | null;
  /* Niveau CUMULE (b) : cumul depuis janvier vs budget cumule A DATE. */
  budget_cumule_a_date: number;
  ecart_a_date: number;
  pct_realisation_a_date: number | null;
};

export type ReponseBudget = {
  arrete: string;
  exercice: number;
  mois: number;
  hypothese: string;
  /** Arrete servant de base au realise mensuel, ou null. */
  precedent: string | null;
  niveau_mensuel_disponible: boolean;
  motif_mensuel_absent: string | null;
  lignes: LigneBudget[];
};

/**
 * Un rapport du moteur en pourcentage affichable.
 * Voir le piege n°1 en tete de fichier : c'est la SEULE conversion autorisee.
 */
export function enPourcent(rapport: number | null | undefined): number | null {
  if (rapport === null || rapport === undefined || !Number.isFinite(rapport)) return null;
  return rapport * 100;
}

/* --------------------------------------------------------------------------
   Les trois lectures — doctrine figee avec le CDG (CLAUDE.md, Rapport 4).
   Chacune repond a une QUESTION differente ; les confondre est l'erreur que
   cette page existe pour empecher.
   -------------------------------------------------------------------------- */

export type CleNiveau = "mensuel" | "annuel" | "a_date";

export type Niveau = {
  cle: CleNiveau;
  onglet: string;
  titre: string;
  /** Ce a quoi ce niveau repond, en une phrase. */
  question: string;
  /** Comment le realise est obtenu — dit a l'ecran, pas seulement ici. */
  provenance: string;
  champBudget: keyof LigneBudget;
  champRealise: keyof LigneBudget;
  champEcart: keyof LigneBudget;
  champPct: keyof LigneBudget;
  intituleBudget: string;
  intituleRealise: string;
  intitulePct: string;
};

export const NIVEAUX: Record<CleNiveau, Niveau> = {
  mensuel: {
    cle: "mensuel",
    onglet: "Mensuel",
    titre: "Realisation du mois",
    question: "Ce mois-ci, a-t-on depense (ou encaisse) ce qui etait prevu pour le mois ?",
    provenance: "Realise du mois = cumul de l'arrete − cumul du mois precedent.",
    champBudget: "budget_mois",
    champRealise: "realise_mois",
    champEcart: "ecart_mois",
    champPct: "pct_realisation",
    intituleBudget: "Budget du mois",
    intituleRealise: "Realise du mois",
    intitulePct: "% de realisation",
  },
  annuel: {
    cle: "annuel",
    onglet: "Progression annuelle",
    titre: "Consommation du budget annuel",
    question: "Depuis janvier, quelle part du budget de l'annee a-t-on consommee ?",
    provenance: "Realise cumule = la balance telle qu'elle arrive, cumulee depuis janvier.",
    champBudget: "budget_annuel",
    champRealise: "realise_cumule",
    champEcart: "ecart_annuel",
    champPct: "pct_progression",
    intituleBudget: "Budget annuel",
    intituleRealise: "Realise cumule",
    intitulePct: "% de progression",
  },
  a_date: {
    cle: "a_date",
    onglet: "Realisation a date",
    titre: "Realisation a date",
    question: "A ce stade de l'annee, est-on en avance ou en retard sur ce qui etait prevu ?",
    provenance:
      "Realise cumule compare au budget des seuls mois ecoules (budget non lineaire).",
    champBudget: "budget_cumule_a_date",
    champRealise: "realise_cumule",
    champEcart: "ecart_a_date",
    champPct: "pct_realisation_a_date",
    intituleBudget: "Budget cumule a date",
    intituleRealise: "Realise cumule",
    intitulePct: "% de realisation a date",
  },
};

export const ORDRE_NIVEAUX: CleNiveau[] = ["mensuel", "annuel", "a_date"];

export function estCleNiveau(valeur: unknown): valeur is CleNiveau {
  return typeof valeur === "string" && valeur in NIVEAUX;
}

/* --------------------------------------------------------------------------
   Lecture d'un ecart
   -------------------------------------------------------------------------- */

export type Tendance = "favorable" | "defavorable" | null;

/**
 * Sens de lecture d'un ecart, selon la nature de la ligne.
 *
 * Depenser MOINS que prevu est favorable ; encaisser moins l'est rarement. Un
 * ecart nu, sans cette lecture, se lit a l'envers une fois sur deux en reunion.
 *
 * `null` dans deux cas, tous deux volontaires : ecart nul (rien a signaler), et
 * sens inconnu — le mapping budgetaire est une table EDITABLE, une ligne peut
 * y arriver sans sens renseigne, et deviner vaudrait alors un verdict inverse.
 */
export function tendance(sens: SensLigne, ecart: number): Tendance {
  if (!Number.isFinite(ecart) || ecart === 0) return null;
  if (sens === "charge") return ecart > 0 ? "defavorable" : "favorable";
  if (sens === "produit") return ecart > 0 ? "favorable" : "defavorable";
  return null;
}

export const LIBELLES_SENS: Record<string, string> = {
  charge: "Charges",
  produit: "Produits",
};

/** Groupes d'affichage : charges, produits, puis tout sens non renseigne. */
export function grouperParSens(lignes: LigneBudget[]): { sens: string; lignes: LigneBudget[] }[] {
  const groupes = new Map<string, LigneBudget[]>();
  for (const l of lignes) {
    const cle = l.sens || "?";
    const existant = groupes.get(cle);
    if (existant) existant.push(l);
    else groupes.set(cle, [l]);
  }
  const ordre = (sens: string) => (sens === "charge" ? 0 : sens === "produit" ? 1 : 2);
  return [...groupes.entries()]
    .map(([sens, lignes]) => ({ sens, lignes }))
    .sort((a, b) => ordre(a.sens) - ordre(b.sens) || a.sens.localeCompare(b.sens));
}

/**
 * Total d'un groupe pour un niveau donne.
 *
 * Le pourcentage du total est RECALCULE sur les totaux (somme des realises ÷
 * somme des budgets), jamais moyenne sur les pourcentages des lignes : une
 * moyenne de taux donne a une ligne de 200 USD le meme poids qu'a une ligne de
 * 200 000, et le total affiche ne correspond alors a rien de calculable.
 */
export function totaliser(lignes: LigneBudget[], niveau: Niveau) {
  const budget = lignes.reduce((s, l) => s + (Number(l[niveau.champBudget]) || 0), 0);
  const realise = lignes.reduce((s, l) => s + (Number(l[niveau.champRealise]) || 0), 0);
  return {
    budget,
    realise,
    ecart: realise - budget,
    pct: budget === 0 ? null : (realise / budget) * 100,
  };
}

/** Un mois en toutes lettres, pour l'entete (le moteur renvoie un numero). */
export const MOIS = [
  "janvier", "fevrier", "mars", "avril", "mai", "juin",
  "juillet", "aout", "septembre", "octobre", "novembre", "decembre",
];

export function nomMois(mois: number): string {
  return MOIS[mois - 1] ?? String(mois);
}
