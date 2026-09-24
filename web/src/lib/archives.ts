/**
 * PopPilot — module ARCHIVES : types des reponses de l'API (api/archives.py).
 */

export type Archive = {
  id: number;
  titre: string;
  type_rapport: string | null;
  periode: string | null;
  format: string;
  version: number;
  depose_par: string | null;
  date_depot: string | null;
  remplace_id: number | null;
  editable: boolean;
};

export type ListeArchives = { archives: Archive[]; types: string[] };

export type DonneesArchive = {
  archive: Archive;
  grille: string[][];
  nb_modifications: number;
  derniere_modification: { par: string; le: string } | null;
};

export type IndicateurSerie = {
  indicateur: string;
  unite: string | null;
  points: number;
  du: string;
  au: string;
};

export type CatalogueSeries = {
  indicateurs: IndicateurSerie[];
  agences: string[];
  arretes_non_alimentes: string[];
};

export type PointSerie = { date: string; valeur: number; unite: string | null; source: string };
export type Serie = { indicateur: string; agence: string | null; points: PointSerie[] };

export type EtatArchive =
  | { etat: "vierge" }
  | { etat: "succes"; message: string }
  | { etat: "echec"; message: string };

/** Libelles lisibles des indicateurs calcules par les moteurs (engine/series.py). */
export const LIBELLES_INDICATEUR: Record<string, string> = {
  encours_credit: "Encours de credit",
  par1: "PAR1 (montant)",
  par30: "PAR30 (montant)",
  par90: "PAR90 (montant)",
  pct_par30: "PAR30 (% de l'encours)",
  nb_credits: "Nombre de credits",
  provisions: "Provisions",
  epargne: "Epargne",
};
