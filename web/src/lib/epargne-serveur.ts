import "server-only";

/**
 * PopPilot — chargement du module EPARGNE.
 *
 * Un seul appel : GET /epargne?arrete=… , qui renvoie deja la synthese ET le
 * nombre d'epargnants (l'API les assemble cote moteur, cf. endpoint_epargne).
 *
 * Cloisonnement : l'endpoint est reserve a ROLES_ACCES_TOTAL. L'inventaire
 * depot n'est pas porteur d'une colonne agence exploitee par ce moteur — la
 * synthese est institutionnelle par construction. On ne la demande donc pas
 * pour un role AGENCE : aller chercher un 403 pour l'afficher ferait passer
 * une regle pour une panne.
 */
import { appelerApi } from "@/lib/api";
import { epargneDemo } from "@/lib/demo";
import { aAccesTotal, type Profil } from "@/lib/roles";
import type { SourceDonnees } from "@/lib/source";
import type { ReponseEpargne } from "@/lib/epargne";

export type TableauEpargne = {
  arrete: string;
  source: SourceDonnees;
  donnees: ReponseEpargne | null;
  erreurApi: string | null;
};

export async function chargerEpargne(
  arrete: string,
  profil: Profil,
  jeton: string | null,
): Promise<TableauEpargne> {
  const reponse = await appelerApi<ReponseEpargne>(
    `/epargne?arrete=${encodeURIComponent(arrete)}`,
    jeton,
  );

  if (reponse.ok) {
    return { arrete, source: "api", donnees: reponse.donnees, erreurApi: null };
  }

  // Repli d'illustration : uniquement en mode demonstration, lui-meme
  // impossible en production et eteint des que Supabase est branche.
  if (profil.demo) {
    return {
      arrete,
      source: "demonstration",
      donnees: epargneDemo(arrete),
      erreurApi: reponse.erreur,
    };
  }

  return { arrete, source: "api", donnees: null, erreurApi: reponse.erreur };
}

/** Raison de refus a afficher, ou null quand le profil a bien acces. */
export function refusEpargne(profil: Profil): string | null {
  if (aAccesTotal(profil)) return null;
  return (
    "La synthese de l'epargne porte sur l'inventaire depot de l'institution entiere " +
    "et alimente un ratio reglementaire (liquidite E4) : elle est reservee aux roles " +
    "DIRECTION, CDG et AUDIT. Le tableau de bord credit reste accessible sur le " +
    "perimetre de votre agence."
  );
}
