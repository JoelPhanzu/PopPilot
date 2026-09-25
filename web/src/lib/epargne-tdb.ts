/**
 * PopPilot — tableau de bord EPARGNE (GET /epargne/tableau-de-bord, GET /epargne/top).
 *
 * Doctrine flux / stock : STOCKS a l'inventaire de l'arrete (encours, comptes,
 * epargnants) ; FLUX (depots, retraits) sur les inventaires de la periode — par
 * MOIS entiers, l'inventaire donnant les mouvements du mois. Montants « encours »,
 * « depots », « retraits » : USD HOMOGENES (CDF converti au taux du mois).
 * `encours_cdf_origine` / `encours_usd_origine` : devise d'origine, non sommables.
 */
export type LigneEpargneTdb = {
  designation: string;
  cle: string | null;
  /** Niveau client : nom complet et statut juridique (null si inventaire importe avant le 25/09/2026). */
  nom_client: string | null;
  statut_juridique: string | null;
  /** Niveau produit : type de depot et devise du produit. */
  type_depot: string | null;
  devise: string | null;
  encours: number;
  encours_usd_origine: number;
  encours_cdf_origine: number;
  nb_comptes: number;
  nb_comptes_crediteurs: number;
  a_vue: number;
  a_terme: number;
  obligatoire: number;
  nb_epargnants: number;
  encours_m1: number | null;
  croissance: number | null;
  depots: number;
  retraits: number;
  collecte_nette: number;
  nb_depots: number;
  nb_retraits: number;
  encours_credit: number | null;
  couverture_credit: number | null;
};

export type TableauDeBordEpargne = {
  arrete: string;
  debut: string;
  fin: string;
  precedent: string | null;
  niveau: "agence" | "produit" | "type" | "client";
  filtres: Record<string, string>;
  taux_change: number;
  inventaires_disponibles: string[];
  mois_de_flux: string[];
  flux_par_mois: { mois: string; depots: number; retraits: number }[];
  nb_lignes_total: number;
  lignes: LigneEpargneTdb[];
  message: string | null;
};

export type TopEpargnants = {
  arrete: string;
  n: number;
  clients: {
    id_client: string;
    /** Nom complet de l'inventaire ; null si l'inventaire a ete importe avant le 25/09/2026. */
    nom_client: string | null;
    statut_juridique: string | null;
    agence: string | null;
    nb_comptes: number;
    solde_usd: number;
  }[];
};

export const NIVEAUX_EPARGNE = [
  { cle: "agence", libelle: "Agences" },
  { cle: "produit", libelle: "Produits" },
  { cle: "type", libelle: "Types de depot" },
  { cle: "client", libelle: "Clients" },
] as const;

/** Filtres proposes en pastilles (valeurs fixes cote moteur). */
export const FILTRES_EPARGNE = [
  { cle: "devise", libelle: "Devise", valeurs: [["USD", "USD"], ["CDF", "CDF"]] },
  { cle: "type_depot", libelle: "Type", valeurs: [["a_vue", "A vue"], ["a_terme", "A terme"], ["obligatoire", "Obligatoire"]] },
  { cle: "sexe", libelle: "Sexe", valeurs: [["H", "Hommes"], ["F", "Femmes"], ["PM", "Sans sexe (PM / groupes)"]] },
  // Statut juridique du TITULAIRE (code CBS 1 / 2 / 4), independant des produits de groupe.
  { cle: "statut", libelle: "Statut juridique", valeurs: [["pp", "Personnes physiques"], ["pm", "Personnes morales seulement"], ["groupe", "Groupes solidaires"]] },
  { cle: "groupe", libelle: "Produits de groupe", valeurs: [["oui", "Groupes seulement"], ["non", "Hors groupes"]] },
] as const;

export const CLES_FILTRES_EPARGNE = ["agence", "devise", "type_depot", "sexe", "statut", "groupe"] as const;
