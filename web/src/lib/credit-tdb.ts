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
  cout_du_risque: number | null;
  entree_par_nb: number | null;
  entree_par_montant: number | null;
  migration_vers: Record<string, number> | null;
  encours_m1: number;
  nb_clients_m1: number;
  nb_credits_m1: number;
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
  niveau: "agence" | "superviseur" | "agent";
  roster_du_mois: boolean;
  message: string | null;
  p15_periode: [string, string];
  nb_prets_selectionnes: number;
  lignes: LigneTdb[];
  decaissements_jour: JourDecaissement[];
  complement_daf_exclu: boolean;
  objectifs_applicables: boolean;
  reserves_masques?: string[];
};

export const NIVEAUX_TDB = [
  { cle: "agence", libelle: "Agences" },
  { cle: "superviseur", libelle: "Superviseurs" },
  { cle: "agent", libelle: "Agents de credit" },
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
