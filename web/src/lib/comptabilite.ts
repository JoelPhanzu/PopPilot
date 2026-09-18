/**
 * PopPilot — domaine COMPTABILITE & INDICATEURS : ce que renvoient les moteurs.
 *
 * Les types suivent la sortie REELLE de `engine/etats_financiers.py` et
 * `engine/indicateurs.py`, relevee sur la base de test, et non une lecture
 * approximative du code. Rien n'est recalcule ici : le bilan, le resultat et
 * les 17 ratios sont produits par les moteurs valides au centime.
 *
 * La seule chose que ce module DERIVE est la confrontation d'une valeur a sa
 * norme (« < 5 % »), pour signaler d'un coup d'oeil ce qui sort des clous.
 * C'est de la lecture, pas du calcul d'indicateur — et c'est volontairement
 * prudent : une norme dont la forme n'est pas reconnue ne recoit AUCUN verdict.
 */

/** Une rubrique de bilan : « Immobilisations », « Fonds propres »… → montant. */
export type Rubriques = Record<string, number>;

export type ControlesEtats = {
  /** Actif − Passif. Doit rester a quelques centimes de zero. */
  bilan_equilibre_ecart: number;
  resultat_net: number;
  resultat_comptable: number;
  /** L'IBP (§67) n'est deduit qu'a l'arrete annuel, grille DAF en main. */
  ibp_deduit: boolean;
  ibp_du_a_cet_arrete: boolean;
  comptes_non_mappes: number;
  fonds_propres: number;
  /** Renseigne quand le taux du mois manque : les montants CDF sont alors absents. */
  taux_absent: string | null;
};

export type EtatsFinanciers = {
  taux_change: number | null;
  actif: Rubriques;
  passif: Rubriques;
  total_actif: number;
  total_passif: number;
  produits: number;
  charges: number;
  resultat_net: number;
  resultat_comptable: number;
  resultat_net_cdf: number | null;
  controles: ControlesEtats;
  /** Numeros de comptes que le mapping ne reconnait pas : a traiter, jamais a ignorer. */
  comptes_non_mappes: string[];
  par_prefixe: Record<string, number>;
};

export type Indicateur = {
  valeur: number | null;
  num: number | null;
  den: number | null;
  /** Norme BCC telle que le moteur l'exprime : « < 5 % », « > 130 », « 13-21 % »… */
  norme: string;
  /** Pourquoi la valeur est absente. Presente ⇒ l'indicateur n'est PAS calcule. */
  motif?: string;
  source?: string;
  /** B2 (emprunteurs par agent) est un rapport, pas un pourcentage. */
  sans_pourcent?: boolean;
};

export type Indicateurs = {
  date_arrete: string;
  par_credit: { date_credit?: string; meme_mois?: boolean } | null;
  /** Faux quand le 31/12 precedent manque : les ratios portent alors sur un solde ponctuel. */
  moyennes_de_periode: boolean;
  date_debut_exercice: string | null;
  /** Ce qui n'a pas pu etre fait, dit explicitement par le moteur. */
  avertissements: Record<string, string>;
  agregats: Record<string, number | null>;
  indicateurs: Record<string, Indicateur>;
};

/* --------------------------------------------------------------------------
   Libelles — repris du catalogue (docs/02_CATALOGUE_INDICATEURS.md), pas
   reformules : un ratio reglementaire se nomme comme la BCC le nomme.
   -------------------------------------------------------------------------- */

export type Famille = "A" | "B" | "C" | "D" | "E";

export const FAMILLES: Record<Famille, string> = {
  A: "Qualite du portefeuille",
  B: "Efficacite et productivite",
  C: "Rentabilite",
  D: "Structure du bilan",
  E: "Normes prudentielles",
};

/** Ordre d'affichage voulu. Un code inconnu n'est pas perdu : il passe en fin. */
export const INDICATEURS_CONNUS: { code: string; famille: Famille; libelle: string }[] = [
  { code: "A1_PAR30", famille: "A", libelle: "PAR 30 (reglementaire)" },
  { code: "A1bis_PAR1", famille: "A", libelle: "PAR 1 (risque global)" },
  { code: "A2_abandon", famille: "A", libelle: "Abandon de creances" },
  { code: "B1_efficacite", famille: "B", libelle: "Efficacite operationnelle" },
  { code: "B2_emprunteurs_agent", famille: "B", libelle: "Emprunteurs par agent" },
  { code: "C1_ROE", famille: "C", libelle: "ROE — rentabilite des fonds propres" },
  { code: "C2_ROA", famille: "C", libelle: "ROA — rentabilite de l'actif" },
  { code: "C3_rendement", famille: "C", libelle: "Rendement du portefeuille" },
  { code: "C4_autosuffisance", famille: "C", libelle: "Autosuffisance operationnelle" },
  { code: "D1_encaisse_oisive", famille: "D", libelle: "Encaisse oisive" },
  { code: "D2_taux_encours", famille: "D", libelle: "Taux d'encours de credit" },
  { code: "D3_immobilisations", famille: "D", libelle: "Taux des immobilisations" },
  { code: "E1_capital_min", famille: "E", libelle: "Capital minimum" },
  { code: "E2_solvabilite", famille: "E", libelle: "Solvabilite" },
  { code: "E3_capitalisation", famille: "E", libelle: "Capitalisation" },
  { code: "E4_liquidite", famille: "E", libelle: "Liquidite immediate" },
  { code: "E5_couverture_immob", famille: "E", libelle: "Couverture des immobilisations" },
  { code: "E6_couverture_emplois_MLT", famille: "E", libelle: "Couverture des emplois MLT" },
];

/** Ce que le numerateur et le denominateur representent, indicateur par indicateur. */
export const COMPOSITION: Record<string, string> = {
  A1_PAR30: "Capital restant du a plus de 30 jours ÷ portefeuille brut",
  A1bis_PAR1: "Capital restant du a au moins 1 jour ÷ portefeuille brut",
  A2_abandon: "Credits radies (≥ 361 j au 31/12) ÷ portefeuille brut moyen",
  B1_efficacite: "Charges de personnel ÷ encours moyen",
  B2_emprunteurs_agent: "Emprunteurs actifs ÷ agents de credit (sans ×100)",
  C1_ROE: "Resultat net ÷ fonds propres moyens",
  C2_ROA: "Resultat net ÷ actif moyen",
  C3_rendement: "Interets et produits du credit ÷ encours moyen",
  C4_autosuffisance: "Total des produits ÷ total des charges",
  D1_encaisse_oisive: "Disponibles (56+57) ÷ total actif",
  D2_taux_encours: "Portefeuille brut ÷ total actif",
  D3_immobilisations: "Immobilisations nettes ÷ total actif",
  E1_capital_min: "Fonds propres de base ÷ 700 000 USD",
  E2_solvabilite: "Fonds propres prudentiels ÷ total actif de la periode (pas de RWA)",
  E3_capitalisation: "Fonds propres de base ÷ total actif",
  E4_liquidite: "Disponibilites ÷ depots a vue",
  E5_couverture_immob: "Immobilisations nettes ÷ fonds propres prudentiels",
  E6_couverture_emplois_MLT: "Ressources stables ÷ emplois stables",
};

/** Agregats mis en avant sous les ratios, avec leur libelle. */
export const LIBELLES_AGREGAT: Record<string, string> = {
  portefeuille_brut: "Portefeuille brut (31+32+39)",
  PAR1_credit: "PAR 1 (source credit)",
  PAR30_credit: "PAR 30 (source credit)",
  capital_retard_bilan_39: "Capital en retard au bilan (compte 39)",
  immob_nettes: "Immobilisations nettes",
  disponibles_56_57: "Disponibles (56+57)",
  depots_a_vue_epargne: "Depots a vue (epargne)",
  depots_cautionnements_27: "Depots et cautionnements (27)",
  total_actif: "Total actif",
  fonds_propres_base: "Fonds propres de base (hors resultat)",
  fonds_propres_prudentiels: "Fonds propres prudentiels (base + 18)",
  fonds_propres_base_avec_resultat: "Fonds propres de base, resultat affecte",
  fonds_propres_prudentiels_avec_resultat: "Fonds propres prudentiels, resultat affecte",
  resultat: "Resultat",
  produits: "Produits",
  charges: "Charges",
  nb_emprunteurs: "Nombre d'emprunteurs actifs",
  nb_agents_roster: "Nombre d'agents (roster)",
};

/** Agregats exprimes en NOMBRE et non en montant : pas de decimales, pas d'USD. */
export const AGREGATS_COMPTAGE = new Set(["nb_emprunteurs", "nb_agents_roster"]);

/* --------------------------------------------------------------------------
   Confrontation a la norme
   -------------------------------------------------------------------------- */

export type Norme =
  | { genre: "seuil"; operateur: "<" | ">" | "≤" | "≥"; seuil: number }
  | { genre: "intervalle"; bas: number; haut: number };

function nombre(brut: string): number | null {
  const n = Number(brut.replace(/\s/g, "").replace(",", "."));
  return Number.isFinite(n) ? n : null;
}

/**
 * Lit une norme telle que le moteur l'ecrit. Toute forme non reconnue renvoie
 * `null` — et sans norme lue, aucun verdict n'est rendu. Un « conforme »
 * affiche a tort sur un ratio reglementaire coute plus cher qu'une case vide.
 */
export function lireNorme(norme: string): Norme | null {
  const texte = (norme ?? "").replace(/%/g, "").trim();

  const intervalle = /^([\d\s.,]+)\s*[-–]\s*([\d\s.,]+)$/.exec(texte);
  if (intervalle) {
    const bas = nombre(intervalle[1]);
    const haut = nombre(intervalle[2]);
    if (bas !== null && haut !== null) return { genre: "intervalle", bas, haut };
    return null;
  }

  const seuil = /^([<>≤≥])\s*([\d\s.,]+)$/.exec(texte);
  if (seuil) {
    const valeur = nombre(seuil[2]);
    if (valeur === null) return null;
    return { genre: "seuil", operateur: seuil[1] as "<" | ">" | "≤" | "≥", seuil: valeur };
  }

  return null;
}

export type Verdict = "conforme" | "hors_norme" | null;

/**
 * Verdict d'un indicateur face a sa norme.
 *
 * `null` dans trois cas, tous volontaires : valeur non calculee, norme non
 * lisible, ou indicateur purement informatif (le PAR 1 n'a pas de seuil BCC).
 * Un indicateur sans verdict s'affiche sans pastille, jamais en « conforme ».
 */
export function verdict(ind: Indicateur): Verdict {
  if (ind.valeur === null || !Number.isFinite(ind.valeur)) return null;
  const norme = lireNorme(ind.norme);
  if (norme === null) return null;

  if (norme.genre === "intervalle") {
    return ind.valeur >= norme.bas && ind.valeur <= norme.haut ? "conforme" : "hors_norme";
  }
  switch (norme.operateur) {
    case "<":
      return ind.valeur < norme.seuil ? "conforme" : "hors_norme";
    case "≤":
      return ind.valeur <= norme.seuil ? "conforme" : "hors_norme";
    case ">":
      return ind.valeur > norme.seuil ? "conforme" : "hors_norme";
    case "≥":
      return ind.valeur >= norme.seuil ? "conforme" : "hors_norme";
  }
}

/** Repartition d'ensemble, pour l'annoncer en tete de page sans la recompter. */
export function bilanDesNormes(indicateurs: Record<string, Indicateur>) {
  let conformes = 0;
  let horsNorme = 0;
  let sansVerdict = 0;
  for (const ind of Object.values(indicateurs)) {
    const v = verdict(ind);
    if (v === "conforme") conformes += 1;
    else if (v === "hors_norme") horsNorme += 1;
    else sansVerdict += 1;
  }
  return { conformes, horsNorme, sansVerdict, total: Object.keys(indicateurs).length };
}

/** Codes presents dans la reponse, dans l'ordre voulu, les inconnus en fin de liste. */
export function ordonner(indicateurs: Record<string, Indicateur>) {
  const connus = INDICATEURS_CONNUS.filter((i) => i.code in indicateurs);
  const vus = new Set(connus.map((i) => i.code));
  const inconnus = Object.keys(indicateurs)
    .filter((code) => !vus.has(code))
    // Un indicateur ajoute cote moteur doit APPARAITRE, meme sans libelle ici :
    // le perdre en silence ferait mentir le decompte affiche.
    .map((code) => ({ code, famille: "E" as Famille, libelle: code }));
  return [...connus, ...inconnus];
}
