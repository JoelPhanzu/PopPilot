/**
 * PopPilot — domaine IMPORT : ce que le formulaire doit savoir de l'API.
 *
 * Le front ne sait RIEN des formats du CBS. Il demande a l'API ce qu'elle
 * accepte (GET /import/domaines) et construit le formulaire a partir de cette
 * reponse. Consequence voulue : le formulaire ne peut jamais proposer un
 * parametre que l'API refuserait, ni en oublier un qu'elle exige — il n'y a pas
 * deux listes a garder en phase, il n'y en a qu'une, cote moteur.
 *
 * Si l'API ne repond pas, l'ecran le DIT et n'affiche pas de formulaire : un
 * import qu'on croit parti alors qu'il n'ira nulle part est pire qu'un ecran vide.
 */

/** Un domaine importable, tel que l'API le decrit. */
export type DomaineImport = {
  cle: string;
  libelle: string;
  extensions: string[];
  /** Champs obligatoires (ex. `date_arrete`), dans l'ordre d'affichage. */
  requis: string[];
  /** Champs facultatifs (ex. `devise`, `feuille`). */
  optionnels: string[];
  aide: string;
};

export type CatalogueImport = {
  /** Base reellement visee par l'API (« PostgreSQL/Supabase (…) » ou repli SQLite). */
  base: string;
  taille_max_mo: number;
  domaines: DomaineImport[];
};

export type LigneJournal = {
  domaine: string;
  fichier: string;
  date_arrete: string | null;
  date_snapshot: string | null;
  acceptees: number;
  rejetees: number;
  horodatage: string | null;
  message: string | null;
};

export type Journal = { base: string; imports: LigneJournal[] };

/** Ce que renvoie POST /import/{domaine} quand tout s'est bien passe. */
export type ResultatImport = {
  domaine: string;
  libelle: string;
  fichier: string;
  octets: number;
  parametres: Record<string, string | number>;
  resultat: Record<string, unknown>;
  lignes_chargees: number;
  base: string;
  importe_par: string;
};

/** Intitules lisibles des champs attendus par les moteurs d'ingestion. */
export const LIBELLES_CHAMP: Record<string, string> = {
  date_arrete: "Date d'arrete",
  date_effet: "Date d'effet",
  feuille: "Feuille du classeur",
  devise: "Devise",
  exercice: "Exercice",
  hypothese: "Hypothese",
};

/** Precisions affichees sous chaque champ — la doctrine, la ou elle s'applique. */
export const AIDES_CHAMP: Record<string, string> = {
  date_arrete:
    "Date COMPTABLE, celle qui fait foi : un fichier recu le 4 mai pour l'arrete du 30 avril se range en avril.",
  date_effet: "Le roster et les objectifs ne valent que pour le mois ou ils prennent effet.",
  feuille: "Laisser vide pour la feuille par defaut du domaine.",
  devise: "La balance USD et la balance CDF d'un meme arrete cohabitent sans s'ecraser.",
  exercice: "Annee budgetaire (ex. 2026).",
  hypothese: "Variante du budget (H1 par defaut).",
};

/** Champs qui doivent s'afficher comme un calendrier plutot qu'un texte libre. */
export function typeDeChamp(champ: string): "date" | "number" | "text" {
  if (champ === "date_arrete" || champ === "date_effet") return "date";
  if (champ === "exercice") return "number";
  return "text";
}

/** Taille lisible d'un envoi (l'inventaire epargne se compte en dizaines de Mo). */
export function poids(octets: number): string {
  if (octets < 1024) return `${octets} o`;
  if (octets < 1024 * 1024) return `${(octets / 1024).toFixed(0)} Ko`;
  return `${(octets / (1024 * 1024)).toFixed(1)} Mo`;
}

/**
 * Etat du formulaire d'import, pour `useActionState`.
 *
 * Il vit ICI et non dans `app/import/actions.ts` : un fichier « use server »
 * ne peut exporter QUE des fonctions asynchrones — chacun de ses exports
 * devient un point d'entree appelable depuis le navigateur. Y laisser une
 * simple constante fait echouer le module entier au chargement, avec
 * « A ‹use server› file can only export async functions, found object ».
 */
export type EtatImport =
  | { etat: "vierge" }
  | { etat: "succes"; resultat: ResultatImport }
  | { etat: "echec"; message: string; statut: number | null };

/** Etat de depart : aucun import tente. */
export const ETAT_INITIAL: EtatImport = { etat: "vierge" };
