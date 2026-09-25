/**
 * PopPilot — regle du calendrier (CDG, 25/09/2026).
 *
 * L'utilisateur choisit N'IMPORTE QUELLE date. L'ecran montre le DERNIER arrete
 * enregistre a cette date (arrete <= date choisie) et AFFICHE cette date-la :
 * 5 juillet → chiffres et date du 30 juin ; 30 juin → 30 juin. Si la date precede
 * tout import : le plus ancien arrete enregistre. Sans date : le plus recent.
 *
 * Les arretes viennent de GET /arretes/{domaine} (ce que la base contient vraiment).
 */
import { appelerApi } from "@/lib/api";
import { dateArreteValide } from "@/lib/format";

export type DomaineArretes = "credit" | "balance" | "epargne" | "compte_resultat_agence";

export type ArreteResolu = {
  /** Arrete effectivement affiche (null : rien d'enregistre). */
  arrete: string | null;
  /** Date saisie dans le calendrier, si elle differe de l'arrete affiche. */
  demande: string | null;
  /** Arretes enregistres, le plus recent d'abord. */
  disponibles: string[];
  /** La liste n'a pas pu etre lue (API muette) : l'ecran garde la date saisie. */
  erreur: string | null;
};

/** Dernier arrete <= date choisie ; sinon le plus ancien ; sans date, le plus recent. */
export function resoudreArrete(demande: string | null | undefined, disponibles: string[]): string | null {
  if (disponibles.length === 0) return null;
  const tries = [...disponibles].sort().reverse();
  if (!demande || !dateArreteValide(demande)) return tries[0];
  return tries.find((a) => a <= demande) ?? tries[tries.length - 1];
}

/** Lit les arretes du domaine et resout la date saisie. */
export async function arreteAffiche(
  domaine: DomaineArretes,
  demande: string | null | undefined,
  jeton: string | null | undefined,
): Promise<ArreteResolu> {
  const saisie = demande && dateArreteValide(demande) ? demande : null;
  const r = await appelerApi<{ arretes: string[] }>(`/arretes/${domaine}`, jeton ?? null);
  if (!r.ok) return { arrete: saisie, demande: null, disponibles: [], erreur: r.erreur };
  const arrete = resoudreArrete(saisie, r.donnees.arretes);
  return {
    arrete,
    demande: saisie && arrete && saisie !== arrete ? saisie : null,
    disponibles: r.donnees.arretes,
    erreur: null,
  };
}
