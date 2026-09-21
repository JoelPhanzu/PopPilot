/**
 * PopPilot — domaine EPARGNE : ce que renvoie GET /epargne.
 *
 * Les types suivent la sortie REELLE de `engine/epargne.py` (synthese_epargne
 * + nb_epargnants). Rien n'est recalcule ici : l'encours, la ventilation et le
 * nombre d'epargnants viennent du moteur, valide contre l'inventaire depot
 * (169 799 comptes, total 6 368 439 USD au 31/07/2026, coherent a 0,6 % pres
 * avec les depots du bilan).
 *
 * UN PIEGE, ET IL EST CENTRAL : le moteur renvoie DEUX familles de montants qui
 * ne vivent pas dans la meme unite.
 *   - `encours_total`, `par_type`, `epargne_groupe`, `depots_*` sont HOMOGENES,
 *     convertis en USD au taux de l'arrete : ils s'additionnent.
 *   - `par_devise_origine` et `par_type_devise` sont en DEVISE D'ORIGINE : des
 *     USD et des CDF cote a cote. Les sommer produirait un nombre qui ne
 *     designe rien (facteur ~2268 entre les deux).
 * D'ou la separation stricte imposee ci-dessous par les types eux-memes.
 */

/** Codes de type de depot produits par la classification CDG. */
export type TypeDepot = "a_vue" | "a_terme" | "obligatoire";

export type ReponseEpargne = {
  date_arrete: string;
  /** « USD » quand les totaux sont convertis, « origine » sinon. */
  devise_totaux: string;
  /** Taux applique a la conversion CDF→USD. Jamais fige (§42). */
  taux_change: number | null;
  /** Encours total, HOMOGENE (converti). */
  encours_total: number;
  nb_comptes: number;
  nb_epargnants: number;
  /** Par type de depot, converti : ces montants s'additionnent. */
  par_type: Record<string, number>;
  /** Par devise, EN DEVISE D'ORIGINE : ces montants ne s'additionnent PAS. */
  par_devise_origine: Record<string, number>;
  /** Cles « type/devise », en devise d'origine. Meme interdit de somme. */
  par_type_devise: Record<string, number>;
  /** Epargne des groupes (Transitoire Groupe + Caution), convertie. */
  epargne_groupe: number;
  depots_a_vue: number;
  depots_a_terme: number;
  depots_obligatoire: number;
};

/** Libelles des types de depot — regle de classification CDG (CLAUDE.md §Epargne). */
export const LIBELLES_TYPE: Record<string, string> = {
  a_vue: "Depots a vue",
  a_terme: "Depots a terme",
  obligatoire: "Epargne obligatoire",
};

/** Ce que chaque type recouvre, tel que le CDG l'a tranche. */
export const COMPOSITION_TYPE: Record<string, string> = {
  a_vue: "Tout ce qui n'est ni a terme ni nanti — denominateur de la liquidite E4",
  a_terme: "Pop Monnaie A Terme + EducaPop A Terme",
  obligatoire: "Pop Monnaie Nantie + Caution Groupes",
};

/** Ordre d'affichage voulu ; un type inconnu passe en fin plutot que d'etre perdu. */
export const TYPES_CONNUS: TypeDepot[] = ["a_vue", "a_terme", "obligatoire"];

export function ordonnerTypes(parType: Record<string, number>): string[] {
  const connus = TYPES_CONNUS.filter((t) => t in parType);
  const vus = new Set<string>(connus);
  return [...connus, ...Object.keys(parType).filter((t) => !vus.has(t))];
}

/**
 * Decoupe `par_type_devise` en un tableau lisible, SANS jamais totaliser deux
 * devises. La cle du moteur a la forme « type/devise » ; une cle qui ne s'y
 * conforme pas est conservee telle quelle plutot qu'ignoree — un produit
 * nouveau doit se voir, meme mal nomme.
 */
export function ventilationParDevise(
  parTypeDevise: Record<string, number>,
): { type: string; devise: string; montant: number }[] {
  return Object.entries(parTypeDevise).map(([cle, montant]) => {
    const coupure = cle.lastIndexOf("/");
    if (coupure === -1) return { type: cle, devise: "?", montant };
    return {
      type: cle.slice(0, coupure),
      devise: cle.slice(coupure + 1),
      montant,
    };
  });
}

/** Devises presentes, dans un ordre stable (USD d'abord, le reste alphabetique). */
export function devisesPresentes(parDevise: Record<string, number>): string[] {
  const codes = Object.keys(parDevise);
  return codes.sort((a, b) => {
    if (a === "USD") return -1;
    if (b === "USD") return 1;
    return a.localeCompare(b);
  });
}

/** Solde moyen par epargnant — division explicite, protegee du zero. */
export function soldeMoyen(encours: number, nbEpargnants: number): number | null {
  if (!Number.isFinite(encours) || !nbEpargnants) return null;
  return encours / nbEpargnants;
}
