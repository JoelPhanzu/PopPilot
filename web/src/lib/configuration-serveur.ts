import "server-only";

/**
 * PopPilot — chargement de la page Configuration.
 *
 * Trois appels en parallele : les parametres de l'arrete, le mapping
 * budgetaire et le referentiel des agences. Ils ne dependent pas les uns des
 * autres, et chaque echec est rapporte SEPAREMENT — une section indisponible
 * ne doit pas faire disparaitre les deux autres sans explication.
 *
 * Pas de repli de demonstration ici, et c'est deliberatif : cette page ECRIT
 * dans le socle. Proposer des formulaires alimentes par des valeurs
 * d'illustration inviterait a saisir dans le vide.
 */
import { appelerApi } from "@/lib/api";
import { peutEcrire, type Profil } from "@/lib/roles";
import type {
  ConfigurationArrete,
  MappingBudget,
  ReponseAgences,
} from "@/lib/configuration";

export type TableauConfiguration = {
  arrete: string;
  parametres: ConfigurationArrete | null;
  mapping: MappingBudget | null;
  agences: ReponseAgences | null;
  erreurParametres: string | null;
  erreurMapping: string | null;
  erreurAgences: string | null;
};

export async function chargerConfiguration(
  arrete: string,
  jeton: string | null,
): Promise<TableauConfiguration> {
  const parametre = encodeURIComponent(arrete);

  const [params, mapping, agences] = await Promise.all([
    appelerApi<ConfigurationArrete>(`/configuration/arrete?arrete=${parametre}`, jeton),
    appelerApi<MappingBudget>("/configuration/mapping-budget", jeton),
    appelerApi<ReponseAgences>("/agences", jeton),
  ]);

  return {
    arrete,
    parametres: params.ok ? params.donnees : null,
    mapping: mapping.ok ? mapping.donnees : null,
    agences: agences.ok ? agences.donnees : null,
    erreurParametres: params.ok ? null : params.erreur,
    erreurMapping: mapping.ok ? null : mapping.erreur,
    erreurAgences: agences.ok ? null : agences.erreur,
  };
}

/**
 * Raison de refus, ou null.
 *
 * L'ECRITURE est exigee ici, pas seulement l'acces total : l'AUDIT lit tout
 * mais n'alimente rien — un controleur ne remplit pas ce qu'il controle
 * (meme regle que pour l'import, cf. ROLES_ECRITURE cote API).
 */
export function refusConfiguration(profil: Profil): string | null {
  if (peutEcrire(profil)) return null;
  return (
    "La configuration des arretes (taux de change, provisions manuelles, " +
    "reintegrations fiscales, mapping budgetaire, referentiel des agences) engage " +
    "tous les calculs de la plateforme : elle est reservee aux roles DIRECTION et " +
    "CDG. Un role AUDIT lit les chiffres qui en decoulent, mais ne les parametre pas."
  );
}
