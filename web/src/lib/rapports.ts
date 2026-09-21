/**
 * PopPilot — domaine RAPPORTS REGLEMENTAIRES.
 *
 * Le formulaire est ENTIEREMENT construit a partir du catalogue renvoye par
 * l'API (GET /rapports) : fichiers attendus, extensions, champs obligatoires
 * ou non, et jusqu'aux textes d'aide. Rien n'est code en dur ici — ajouter un
 * rapport cote moteur le fait apparaitre a l'ecran sans toucher au front.
 *
 * C'est le meme parti que l'import CBS, et pour la meme raison : la liste de ce
 * qu'il faut fournir appartient au cote qui sait de quoi les moteurs ont
 * besoin. Deux listes finiraient par se contredire, et l'ecran demanderait un
 * fichier que le moteur n'attend plus.
 */

export type TypeChamp = "date" | "texte" | "nombre" | "entier";

export type ChampRapport = {
  nom: string;
  libelle: string;
  type: TypeChamp;
  obligatoire: boolean;
  aide: string;
};

export type FichierRapport = {
  nom: string;
  libelle: string;
  extensions: string[];
  obligatoire: boolean;
  aide: string;
};

export type Rapport = {
  cle: string;
  libelle: string;
  description: string;
  aide: string;
  /**
   * Le gabarit officiel de la BCC est-il rempli ?
   *
   * Faux pour le systeme de paiement : la plateforme produit alors un classeur
   * de RESULTATS, pas la declaration. La difference doit se voir a l'ecran —
   * quelqu'un qui telecharge un fichier nomme « Systeme_paiement » pourrait
   * sinon le transmettre en croyant tenir la declaration officielle.
   */
  remplit_gabarit: boolean;
  extension_sortie: string;
  fichiers: FichierRapport[];
  champs: ChampRapport[];
};

export type CatalogueRapports = { rapports: Rapport[] };

/** Etat du formulaire de generation (meme contrat que l'import). */
export type EtatRapport =
  | { etat: "vierge" }
  | { etat: "echec"; statut: number | null; message: string };

export const ETAT_RAPPORT_INITIAL: EtatRapport = { etat: "vierge" };

/** Type de champ HTML pour un champ du catalogue. */
export function typeHtml(type: TypeChamp): string {
  if (type === "date") return "date";
  if (type === "nombre" || type === "entier") return "number";
  return "text";
}

/** Pas de saisie : un effectif s'exprime en entiers, une part en decimales. */
export function pasDeSaisie(type: TypeChamp): string | undefined {
  if (type === "entier") return "1";
  if (type === "nombre") return "any";
  return undefined;
}

/** Extensions acceptees, pretes pour l'attribut `accept` d'un champ fichier. */
export function accepte(fichier: FichierRapport): string {
  return fichier.extensions.join(",");
}
