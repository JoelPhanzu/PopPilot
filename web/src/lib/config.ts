/**
 * PopPilot — configuration lue depuis l'environnement.
 *
 * Tant que `web/.env.local` est au gabarit ([A_REMPLIR]), Supabase n'est PAS
 * configure. On le detecte explicitement plutot que de laisser le front planter
 * sur une URL invalide : meme logique que `env_encore_gabarit()` cote API
 * (api/socle/schema.py), qui refuse de faire passer un gabarit pour une config.
 */

export const URL_SUPABASE = (process.env.NEXT_PUBLIC_SUPABASE_URL ?? "").trim();
export const CLE_ANON_SUPABASE = (process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "").trim();
export const URL_API = (process.env.NEXT_PUBLIC_POPPILOT_API ?? "http://localhost:8000").trim();

/** Une valeur encore au gabarit ne compte pas comme configuree. */
function estGabarit(valeur: string): boolean {
  return valeur === "" || /^\[?A_REMPLIR\]?$/i.test(valeur);
}

/** Vrai seulement si l'URL et la cle anonyme sont reellement renseignees. */
export function supabaseConfigure(): boolean {
  if (estGabarit(URL_SUPABASE) || estGabarit(CLE_ANON_SUPABASE)) return false;
  return /^https?:\/\//i.test(URL_SUPABASE);
}

/**
 * Mode demonstration : permet de parcourir l'interface (et de verifier le
 * cloisonnement par role) AVANT que Supabase ne soit branche.
 *
 * DEUX verrous, car ce mode contourne l'authentification :
 *   1. il s'eteint des que Supabase est configure ;
 *   2. il est impossible en production (NODE_ENV === "production").
 * Il ne peut donc jamais servir de porte derobee sur un deploiement reel.
 */
export function modeDemoAutorise(): boolean {
  return !supabaseConfigure() && process.env.NODE_ENV !== "production";
}

/** Ce qu'il manque pour sortir du gabarit — affiche a l'ecran de connexion. */
export function configurationAFaire(): string | null {
  if (supabaseConfigure()) return null;
  const manquantes: string[] = [];
  if (estGabarit(URL_SUPABASE)) manquantes.push("NEXT_PUBLIC_SUPABASE_URL");
  if (estGabarit(CLE_ANON_SUPABASE)) manquantes.push("NEXT_PUBLIC_SUPABASE_ANON_KEY");
  if (manquantes.length === 0) {
    return "NEXT_PUBLIC_SUPABASE_URL doit commencer par https://";
  }
  return `A renseigner dans web/.env.local : ${manquantes.join(", ")}`;
}
