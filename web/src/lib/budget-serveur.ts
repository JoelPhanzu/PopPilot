import "server-only";

/**
 * PopPilot — chargement du module BUDGET.
 *
 * Un seul appel : GET /budget?arrete=… . L'exercice et le mois ne sont PAS
 * transmis — l'API les deduit de l'arrete. Les envoyer d'ici rouvrirait
 * exactement la faille que l'endpoint ferme : comparer le realise d'un mois au
 * budget d'un autre sans qu'aucun controle ne s'en apercoive.
 *
 * Cloisonnement : endpoint reserve a ROLES_ACCES_TOTAL (verifie par
 * tests/test_budget_api.py). Le suivi budgetaire est un agregat d'institution.
 */
import { appelerApi } from "@/lib/api";
import { budgetDemo } from "@/lib/demo";
import { aAccesTotal, type Profil } from "@/lib/roles";
import type { SourceDonnees } from "@/lib/source";
import type { ReponseBudget } from "@/lib/budget";

export type TableauBudget = {
  arrete: string;
  source: SourceDonnees;
  donnees: ReponseBudget | null;
  erreurApi: string | null;
};

export async function chargerBudget(
  arrete: string,
  profil: Profil,
  jeton: string | null,
  hypothese?: string,
): Promise<TableauBudget> {
  const parametres = new URLSearchParams({ arrete });
  // L'hypothese n'est transmise que si elle est demandee : l'API a son propre
  // defaut (« H1 »), et le front n'a pas a le dupliquer ni a le contredire.
  if (hypothese) parametres.set("hypothese", hypothese);

  const reponse = await appelerApi<ReponseBudget>(`/budget?${parametres}`, jeton);

  if (reponse.ok) {
    return { arrete, source: "api", donnees: reponse.donnees, erreurApi: null };
  }

  if (profil.demo) {
    return {
      arrete,
      source: "demonstration",
      donnees: budgetDemo(arrete),
      erreurApi: reponse.erreur,
    };
  }

  return { arrete, source: "api", donnees: null, erreurApi: reponse.erreur };
}

/** Raison de refus a afficher, ou null quand le profil a bien acces. */
export function refusBudget(profil: Profil): string | null {
  if (aAccesTotal(profil)) return null;
  return (
    "Le suivi budgetaire confronte la balance de l'institution au budget vote : " +
    "il est reserve aux roles DIRECTION, CDG et AUDIT. Le tableau de bord credit " +
    "reste accessible sur le perimetre de votre agence."
  );
}
