/**
 * PopPilot — configuration lue depuis l'environnement.
 *
 * Tant que `web/.env.local` est au gabarit ([A_REMPLIR]), Supabase n'est PAS
 * configure. On le detecte explicitement plutot que de laisser le front planter
 * sur une URL invalide : meme logique que `env_encore_gabarit()` cote API
 * (api/socle/schema.py), qui refuse de faire passer un gabarit pour une config.
 */

/** Retire espaces et guillemets residuels autour d'une valeur d'environnement. */
function nettoyer(valeur: string | undefined): string {
  return (valeur ?? "").trim().replace(/^["']|["']$/g, "");
}

/** Valeur brute de l'URL, telle qu'elle est ecrite dans .env.local. */
const URL_BRUTE = nettoyer(process.env.NEXT_PUBLIC_SUPABASE_URL);

/**
 * supabase-js veut l'URL RACINE du projet : il ajoute lui-meme `/auth/v1`,
 * `/rest/v1`, `/storage/v1`… Une URL qui porte deja un chemin (le
 * `https://xxx.supabase.co/rest/v1/` qu'on copie machinalement depuis la
 * console) produit des appels vers `/rest/v1/auth/v1/token`, et Supabase
 * repond « Invalid path specified in request URL » — message qui ne dit nulle
 * part que la faute est dans la variable d'environnement.
 *
 * On ne garde donc que l'ORIGINE : chemin, slash final, requete et fragment
 * sont ecartes ici, une bonne fois, plutot qu'a chaque appel.
 */
function origine(brut: string): string {
  if (!/^https?:\/\//i.test(brut)) return "";
  try {
    return new URL(brut).origin;
  } catch {
    return "";
  }
}

export const URL_SUPABASE = origine(URL_BRUTE);
export const CLE_ANON_SUPABASE = nettoyer(process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY);
export const URL_API = nettoyer(process.env.NEXT_PUBLIC_POPPILOT_API) || "http://localhost:8000";

/**
 * Delai d'attente des appels a l'API, en millisecondes (defaut 30 s).
 *
 * Les moteurs calculent sur la base Supabase distante : le PAR se parcourt
 * pret par pret, et le temps de reponse suit la taille du portefeuille. Il n'y
 * a donc pas de bonne valeur universelle — d'ou la variable. Une valeur
 * illisible ou nulle retombe sur le defaut plutot que de produire un
 * `AbortSignal.timeout(NaN)`, qui couperait l'appel immediatement.
 */
export const DELAI_API_MS: number = (() => {
  const brut = Number(nettoyer(process.env.NEXT_PUBLIC_POPPILOT_API_TIMEOUT_MS));
  return Number.isFinite(brut) && brut > 0 ? brut : 30_000;
})();

/**
 * Ce qui a ete retire de l'URL, s'il y avait quelque chose en trop.
 * Sert a le DIRE au lieu de corriger en silence : la prochaine personne qui
 * ouvre .env.local doit y trouver une valeur juste, pas un front qui rattrape.
 */
export function residuUrlSupabase(): string | null {
  if (URL_SUPABASE === "" || URL_BRUTE === URL_SUPABASE) return null;
  return URL_BRUTE;
}

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
    return "NEXT_PUBLIC_SUPABASE_URL doit etre une URL https complete.";
  }
  return `A renseigner dans web/.env.local : ${manquantes.join(", ")}`;
}

/**
 * Anomalie de configuration a signaler alors que l'application FONCTIONNE :
 * l'URL a ete ramenee a son origine, mais .env.local reste a corriger.
 */
export function avertissementConfiguration(): string | null {
  const residu = residuUrlSupabase();
  if (residu === null) return null;
  return (
    `NEXT_PUBLIC_SUPABASE_URL contient autre chose que l'URL racine du projet ` +
    `(« ${residu} »). Elle a ete ramenee a « ${URL_SUPABASE} » pour cette session. ` +
    `Corriger web/.env.local : l'URL racine, sans /rest/v1 ni slash final.`
  );
}
