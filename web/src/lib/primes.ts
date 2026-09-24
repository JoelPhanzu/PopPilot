/**
 * PopPilot — domaine PRIMES (hors « AC et SUP ») : types des reponses de l'API.
 *
 * Aucun calcul ici : les montants viennent de engine/moteur_primes.py via
 * api/primes.py. L'ecran affiche, il ne recalcule pas.
 */

export type LigneDirectionAgence = {
  agence: string;
  resultat: number;
  prime_chef_agence: number;
  prime_adjoint: number;
  motif: string;
};

export type PrimesDirection = {
  arrete: string;
  agences: LigneDirectionAgence[];
  direction_generale: { resultat_total: number; primes: Record<string, number>; motif: string };
};

export type LigneSupport = {
  agence: string;
  taux_decaissement: number | null;
  par30: number;
  couverture: number;
  effectif: number | null;
  prime_decaissement: number;
  prime_epargne: number;
  prime_par: number;
  prime_unitaire: number;
  prime_totale_agence: number;
  objectif_connu: boolean;
  effectif_saisi: boolean;
};

export type PrimesSupport = {
  arrete: string;
  alertes: string[];
  agences: LigneSupport[];
  total: number;
};

export type AgentRecouvrement = {
  equipe: string | null;
  agent: string;
  agence: string | null;
  m91_180: number;
  m181_360: number;
  radie: number;
  prime: number;
};

export type PrimesRecouvrement = {
  fichier: string;
  agents: AgentRecouvrement[];
  total_recouvre: { "91-180": number; "181-360": number; radie: number };
  total_primes_agents: number;
  responsable: { prime: number; detail: Record<string, number> };
  alertes: string[];
};

export type LigneEpargneSuperviseur = {
  agence: string;
  cible: number;
  realisation: number;
  taux: number | null;
  prime: number;
};

export type PrimesSuperviseursEpargne = {
  fichier: string;
  agences: LigneEpargneSuperviseur[];
  total: { cible: number; realisation: number; taux: number | null; prime: number };
  paliers: string;
  alertes: string[];
};

export type EtatAction<T> =
  | { etat: "vierge" }
  | { etat: "succes"; resultat: T }
  | { etat: "echec"; message: string };
