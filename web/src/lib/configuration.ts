/**
 * PopPilot — CONFIGURATION : les intrants saisis a la main (DAF / CDG).
 *
 * Tout ce qui vit ici est un INTRANT de calcul, jamais un resultat. La regle de
 * la maison — « stocker des faits dates, jamais un indicateur calcule » — vaut
 * aussi dans l'autre sens : certains faits ne se deduisent d'aucune donnee et
 * doivent etre SAISIS. Un taux de cloture BCC, une provision decidee par le
 * DAF, une grille fiscale : aucune de ces valeurs n'est dans le CBS.
 *
 * Ce qu'il ne faut pas confondre, et que les types separent :
 *  - le TAUX est versionne a DATE D'EFFET (il vaut jusqu'au suivant) ;
 *  - la PROVISION MANUELLE est attachee a UN ARRETE et a UNE AGENCE ;
 *  - la REINTEGRATION est versionnee a date d'effet, par nature de charge ;
 *  - le MAPPING budgetaire est versionne a date d'effet, par compte.
 */

export type TauxChange = {
  date_effet: string;
  taux: number;
  /** Faux quand le taux applique vient d'un autre mois que l'arrete. */
  du_mois_de_l_arrete: boolean;
};

export type TauxHistorique = {
  id: number;
  date_effet: string;
  taux: number;
};

export type ProvisionManuelle = {
  agence: string;
  montant: number;
  note: string | null;
  saisi_par: string | null;
  horodatage: string | null;
};

export type Reintegration = {
  id: number;
  compte_ou_ligne: string;
  /** FRACTION entre 0 et 1 (0,5 = 50 %), jamais un pourcentage. */
  taux_reintegration: number;
  date_effet: string;
};

export type ConfigurationArrete = {
  arrete: string;
  taux_change: TauxChange | null;
  taux_historique: TauxHistorique[];
  provisions_manuelles: ProvisionManuelle[];
  reintegrations: Reintegration[];
  taux_ibp: number | null;
  agences: string[];
};

export type LigneMapping = {
  numero_compte: string;
  ligne_budgetaire: string;
  sens: string;
  date_effet: string | null;
};

export type MappingBudget = {
  lignes: LigneMapping[];
  nb_comptes: number;
  nb_charges: number;
  nb_produits: number;
  source: string;
};

export type Agence = {
  code_agence: string;
  nom: string | null;
  region: string | null;
  statut: string;
  date_ouverture: string | null;
  date_fermeture: string | null;
  motif: string | null;
};

export type ReponseAgences = {
  agences: Agence[];
  statuts: string[];
};

export const STATUTS_AGENCE = ["ACTIVE", "FERMEE", "SUSPENDUE"] as const;

export const LIBELLES_STATUT: Record<string, string> = {
  ACTIVE: "Active",
  FERMEE: "Fermee",
  SUSPENDUE: "Suspendue",
};

/** Ce que chaque statut implique pour les calculs — dit a l'ecran, pas devine. */
export const EFFET_STATUT: Record<string, string> = {
  ACTIVE: "Agents evalues, orphelins detectes, portefeuille suivi normalement.",
  FERMEE:
    "Portefeuille REEL et declarable a la BCC, mais aucun agent : son encours n'est " +
    "jamais classe « orphelin » ni evalue en performance d'agents.",
  SUSPENDUE:
    "Activite interrompue sans fermeture. Le portefeuille reste suivi ; a trancher " +
    "au cas par cas avec le CDG.",
};

/** Etat d'un formulaire de configuration (meme contrat que l'import). */
export type EtatConfiguration =
  | { etat: "vierge" }
  | { etat: "succes"; message: string }
  | { etat: "echec"; message: string };

export const ETAT_CONFIGURATION_INITIAL: EtatConfiguration = { etat: "vierge" };

/** Un taux de reintegration s'affiche en %, mais se SAISIT et se stocke en fraction. */
export function fractionVersPourcent(fraction: number): number {
  return fraction * 100;
}
