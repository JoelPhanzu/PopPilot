import "server-only";

/**
 * PopPilot — chargement du module Comptabilite & Indicateurs.
 *
 * Deux appels a l'API, en PARALLELE : les etats financiers et les indicateurs
 * prudentiels reposent tous deux sur la balance de l'arrete, mais l'un
 * n'attend pas l'autre. Enchaines, ils doubleraient un temps de reponse deja
 * long (les moteurs calculent sur Supabase).
 *
 * Les deux echecs sont rapportes SEPAREMENT : les indicateurs peuvent manquer
 * alors que le bilan sort, et l'inverse. Un seul message pour les deux ferait
 * disparaitre la moitie de l'ecran sans dire laquelle.
 */
import { appelerApi } from "@/lib/api";
import type { EtatsFinanciers, Indicateurs } from "@/lib/comptabilite";

export type TableauComptabilite = {
  arrete: string;
  etats: EtatsFinanciers | null;
  indicateurs: Indicateurs | null;
  erreurEtats: string | null;
  erreurIndicateurs: string | null;
};

export async function chargerComptabilite(
  arrete: string,
  jeton: string | null,
): Promise<TableauComptabilite> {
  const parametre = encodeURIComponent(arrete);

  const [etats, indicateurs] = await Promise.all([
    appelerApi<EtatsFinanciers>(`/etats-financiers?arrete=${parametre}`, jeton),
    appelerApi<Indicateurs>(`/indicateurs?arrete=${parametre}`, jeton),
  ]);

  return {
    arrete,
    etats: etats.ok ? etats.donnees : null,
    indicateurs: indicateurs.ok ? indicateurs.donnees : null,
    erreurEtats: etats.ok ? null : etats.erreur,
    erreurIndicateurs: indicateurs.ok ? null : indicateurs.erreur,
  };
}
