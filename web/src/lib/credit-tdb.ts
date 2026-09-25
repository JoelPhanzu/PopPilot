/**
 * PopPilot — tableau de bord CREDIT complet (GET /credit/tableau-de-bord).
 *
 * Doctrine flux / stock : les STOCKS (encours, PAR, provisions, clients) sont
 * valorises a la date d'arrete ; les FLUX (decaissements, P15) portent sur la
 * periode [debut ; fin] ; le cout du risque et les migrations comparent l'arrete
 * a l'arrete M-1. Tout vient de l'API — les taux sont des FRACTIONS (0,118),
 * convertis en % a l'affichage seulement.
 */
import type { FiltresCredit } from "@/lib/credit";

export type LigneTdb = {
  agence: string;
  fonction: string;
  designation: string;
  statut: "actif" | "orphelin" | "gele";
  nb_agents: number | null;
  p15_objectif: number | null;
  p15: number;
  objectif_nombre: number | null;
  decaisse_nombre: number;
  pct_realisation_nombre: number | null;
  productivite: number | null;
  objectif_volume: number | null;
  decaisse_volume: number;
  pct_realisation_volume: number | null;
  decaisse_categories: Record<"GL" | "IL" | "PME", { nombre: number; volume: number }>;
  nb_clients: number;
  nb_credits: number;
  encours: number;
  croissance: number | null;
  par1: number;
  par30: number;
  par90: number;
  pct_par1: number;
  pct_par30: number;
  pct_par90: number;
  provisions: number | null;
  complement_daf: number | null;
  provisions_m1: number | null;
  variation_provision: number | null;
  cout_du_risque: number | null;
  entree_par_nb: number | null;
  entree_par_montant: number | null;
  migration_vers: Record<string, number> | null;
  /** Projection au dernier jour du mois si rien n'est recouvre (engine/potentiel.py). */
  potentiel_cout_du_risque: number | null;
  potentiel_migration_nb: number;
  potentiel_migration_montant: number;
  potentiel_migration_vers: Record<string, number> | null;
  encours_m1: number;
  nb_clients_m1: number;
  nb_credits_m1: number;
  /** Encaissements de la periode [debut ; fin] (fichier Credits rembourses). */
  interets_encaisses: number;
  capital_rembourse: number;
  penalites_encaissees: number;
  nb_remboursements: number;
  /** Encaisse sur les dossiers en retard a l'arrete M-1. */
  recouvre_sur_par: number;
};

export type JourDecaissement = {
  date: string;
  nombre: number;
  volume: number;
  cumul_nombre: number;
  cumul_volume: number;
};

export type TableauDeBordCredit = {
  arrete: string;
  debut: string;
  fin: string;
  precedent: string | null;
  niveau: "agence" | "superviseur" | "agent" | "client";
  roster_du_mois: boolean;
  message: string | null;
  p15_periode: [string, string];
  nb_prets_selectionnes: number;
  lignes: LigneTdb[];
  /** Niveau client : nombre total de clients avant la limite d'affichage. */
  nb_lignes_total: number | null;
  decaissements_jour: JourDecaissement[];
  complement_daf_exclu: boolean;
  objectifs_applicables: boolean;
  reserves_masques?: string[];
};

export const NIVEAUX_TDB = [
  { cle: "agence", libelle: "Agences" },
  { cle: "superviseur", libelle: "Superviseurs" },
  { cle: "agent", libelle: "Agents de credit" },
  { cle: "client", libelle: "Clients" },
] as const;

/** Descente dans le tableau : agence → superviseurs → agents → clients. */
export const NIVEAU_SUIVANT: Record<string, { niveau: string; filtre: "agence" | "superviseur" | "agent" }> = {
  agence: { niveau: "superviseur", filtre: "agence" },
  superviseur: { niveau: "agent", filtre: "superviseur" },
  agent: { niveau: "client", filtre: "agent" },
};

export type ArretesCredit = { arretes: { date: string; nb_prets: number }[] };

export type ClientClasse = {
  numero_client: string;
  nom_client: string | null;
  agence: string | null;
  agent: string | null;
  encours: number;
  encours_retard: number;
  max_jours_retard: number;
  nb_credits: number;
  valeur: number;
  premiere_date?: string;
};

export type TopClients = {
  arrete: string;
  n: number;
  critere: "encours" | "decaissement" | "fidelite";
  periode: [string, string] | null;
  nb_clients_selection: number;
  meilleurs: ClientClasse[];
  pires: ClientClasse[];
};

export const TOP_N = [10, 20, 30, 50] as const;
export const CRITERES_TOP = [
  { cle: "encours", libelle: "Encours" },
  { cle: "decaissement", libelle: "Decaisse sur la periode" },
  { cle: "fidelite", libelle: "Fidelite (nb de credits)" },
] as const;

export function requeteTdb(
  p: { arrete: string; debut?: string; fin?: string; niveau?: string },
  f: FiltresCredit,
): string {
  const q = new URLSearchParams({ arrete: p.arrete });
  if (p.debut) q.set("debut", p.debut);
  if (p.fin) q.set("fin", p.fin);
  if (p.niveau) q.set("niveau", p.niveau);
  for (const [k, v] of Object.entries(f)) {
    if (Array.isArray(v)) v.forEach((x) => q.append(k, x));
    else if (v) q.set(k, v);
  }
  return q.toString();
}
