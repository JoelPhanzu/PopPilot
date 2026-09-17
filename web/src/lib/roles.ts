/**
 * PopPilot — roles et cloisonnement par agence (cote front).
 *
 * MIROIR EXACT de api/auth_supabase.py. Le cloisonnement reel tient a DEUX
 * niveaux cote serveur (RLS Supabase + filtre dans l'API) ; ce module est un
 * TROISIEME niveau, purement d'affichage : il evite qu'un ecran demande ou
 * montre ce que l'utilisateur n'a pas le droit de voir. Il ne remplace ni le
 * RLS ni le filtre API — un front ne protege jamais une donnee, il ne fait que
 * ne pas la reclamer.
 */

export const ROLES = ["DIRECTION", "CDG", "AGENCE", "AUDIT"] as const;
export type Role = (typeof ROLES)[number];

/** Roles qui voient toute l'institution (cf. ROLES_ACCES_TOTAL cote API). */
export const ROLES_ACCES_TOTAL: readonly Role[] = ["DIRECTION", "CDG", "AUDIT"];

/** Roles autorises a importer / ecrire (cf. exiger_role cote API). */
export const ROLES_ECRITURE: readonly Role[] = ["DIRECTION", "CDG"];

export type Profil = {
  login: string;
  role: Role;
  /** Agence de rattachement — obligatoire pour le role AGENCE, sinon null. */
  agence: string | null;
  /** Vrai quand le profil vient du mode demonstration (Supabase non branche). */
  demo: boolean;
};

export function estRole(valeur: unknown): valeur is Role {
  return typeof valeur === "string" && (ROLES as readonly string[]).includes(valeur);
}

/** L'utilisateur voit-il toutes les agences ? */
export function aAccesTotal(profil: Profil | null): boolean {
  return profil !== null && ROLES_ACCES_TOTAL.includes(profil.role);
}

/** L'utilisateur peut-il importer / modifier des donnees ? */
export function peutEcrire(profil: Profil | null): boolean {
  return profil !== null && ROLES_ECRITURE.includes(profil.role);
}

/**
 * Un role AGENCE sans agence de rattachement ne voit RIEN (et non pas tout) :
 * en cas de profil incomplet, on ferme, on n'ouvre pas.
 */
export function agencesAutorisees(profil: Profil | null, toutes: string[]): string[] {
  if (profil === null) return [];
  if (aAccesTotal(profil)) return [...toutes];
  if (profil.role === "AGENCE" && profil.agence) return [profil.agence];
  return [];
}

/** Filtre une liste de lignes par agence (equivalent de filtrer_par_agence). */
export function filtrerParAgence<T extends Record<string, unknown>>(
  profil: Profil | null,
  lignes: T[],
  cle: keyof T = "agence" as keyof T,
): T[] {
  if (profil === null) return [];
  if (aAccesTotal(profil)) return lignes;
  const autorisees = new Set(
    agencesAutorisees(profil, lignes.map((l) => String(l[cle]))),
  );
  return lignes.filter((l) => autorisees.has(String(l[cle])));
}

/** Ce que couvre le total affiche : « MICROPOP » ou le nom de l'agence. */
export function porteeAffichee(profil: Profil | null): string {
  if (profil === null) return "—";
  if (aAccesTotal(profil)) return "MICROPOP (toutes agences)";
  return profil.agence ?? "Aucune agence rattachee";
}

export const LIBELLES_ROLE: Record<Role, string> = {
  DIRECTION: "Direction",
  CDG: "Controle de gestion",
  AGENCE: "Agence",
  AUDIT: "Audit (lecture seule)",
};
