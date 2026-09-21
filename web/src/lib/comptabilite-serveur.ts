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
 *
 * Cloisonnement — ce module ne DEMANDE meme pas les donnees a un role qui n'y
 * a pas droit. Cote API, /etats-financiers et /indicateurs sont reserves a
 * ROLES_ACCES_TOTAL (exiger_role) : le bilan et les ratios prudentiels sont
 * des agregats d'institution, qui n'ont aucun sens decoupes par agence. Aller
 * chercher un 403 pour l'afficher ensuite ferait passer une REGLE pour une
 * panne.
 */
import { appelerApi } from "@/lib/api";
import { etatsDemo, indicateursDemo } from "@/lib/demo";
import { aAccesTotal, type Profil } from "@/lib/roles";
import type { SourceDonnees } from "@/lib/source";
import type { EtatsFinanciers, Indicateurs } from "@/lib/comptabilite";

export type TableauComptabilite = {
  arrete: string;
  /** D'ou viennent les chiffres affiches : socle (API) ou illustration. */
  source: SourceDonnees;
  etats: EtatsFinanciers | null;
  indicateurs: Indicateurs | null;
  erreurEtats: string | null;
  erreurIndicateurs: string | null;
};

/**
 * Charge le module pour un profil a acces total.
 *
 * L'appelant garantit le droit d'acces (cf. `aAccesTotal`) : cette fonction ne
 * le revalide pas, elle ne saurait pas quoi renvoyer a un role qui n'a rien a
 * voir ici — c'est a l'ecran de le DIRE, pas a un chargeur de le taire.
 */
export async function chargerComptabilite(
  arrete: string,
  profil: Profil,
  jeton: string | null,
): Promise<TableauComptabilite> {
  const parametre = encodeURIComponent(arrete);

  const [etats, indicateurs] = await Promise.all([
    appelerApi<EtatsFinanciers>(`/etats-financiers?arrete=${parametre}`, jeton),
    appelerApi<Indicateurs>(`/indicateurs?arrete=${parametre}`, jeton),
  ]);

  // Repli d'illustration : uniquement en mode demonstration (profil.demo), qui
  // est lui-meme impossible en production et s'eteint des que Supabase est
  // branche (cf. lib/config.ts). Jamais de chiffre invente pour un vrai
  // compte : hors demonstration, l'ecran reste vide et explique pourquoi.
  if (profil.demo && !etats.ok && !indicateurs.ok) {
    return {
      arrete,
      source: "demonstration",
      etats: etatsDemo(),
      indicateurs: indicateursDemo(arrete),
      erreurEtats: etats.erreur,
      erreurIndicateurs: null,
    };
  }

  return {
    arrete,
    source: "api",
    etats: etats.ok ? etats.donnees : null,
    indicateurs: indicateurs.ok ? indicateurs.donnees : null,
    erreurEtats: etats.ok ? null : etats.erreur,
    erreurIndicateurs: indicateurs.ok ? null : indicateurs.erreur,
  };
}

/** Raison de refus a afficher, ou null quand le profil a bien acces. */
export function refusComptabilite(profil: Profil): string | null {
  if (aAccesTotal(profil)) return null;
  return (
    "Le bilan, le compte de resultat et les indicateurs prudentiels sont des " +
    "agregats de l'institution : ils ne se decoupent pas par agence et sont " +
    "reserves aux roles DIRECTION, CDG et AUDIT. Le tableau de bord credit, lui, " +
    "reste accessible sur le perimetre de votre agence."
  );
}
