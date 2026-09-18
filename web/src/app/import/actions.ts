"use server";

/**
 * PopPilot — action serveur de l'ecran d'import.
 *
 * Elle ne fait que TRANSMETTRE : le fichier va au moteur d'ingestion via
 * POST /import/{domaine}, sans etre lu, decoupe ni interprete ici. Le front ne
 * doit jamais devenir un deuxieme endroit ou l'on sait lire une extraction du
 * CBS — il n'y en a qu'un, `api/ingest/`.
 *
 * Le controle de role est refait ici PAR PRUDENCE, pas par necessite : l'API
 * refuse deja tout appelant hors DIRECTION / CDG (ROLES_ECRITURE). Le refuser
 * aussi cote serveur Next evite d'envoyer un fichier de 40 Mo pour se faire
 * repondre 403 — mais c'est l'API qui protege, jamais cette fonction.
 */
import { revalidatePath } from "next/cache";
import { sessionCourante } from "@/lib/session";
import { peutEcrire } from "@/lib/roles";
import { televerserApi } from "@/lib/api";
import type { EtatImport, ResultatImport } from "@/lib/import";

// L'etat du formulaire (type + valeur initiale) est declare dans
// `@/lib/import` : ce fichier est en « use server », et un tel module ne peut
// exporter que des fonctions asynchrones — chaque export y devient une action
// appelable depuis le navigateur. Une constante exportee ici casse le module
// au chargement (« can only export async functions, found object »).

/** Champs que l'API accepte (cf. DOMAINES dans api/import_cbs.py). */
const CHAMPS = ["date_arrete", "date_effet", "feuille", "devise", "exercice", "hypothese"] as const;

export async function importerFichier(
  _precedent: EtatImport,
  donnees: FormData,
): Promise<EtatImport> {
  const { profil, jeton } = await sessionCourante();

  if (!peutEcrire(profil)) {
    return {
      etat: "echec",
      statut: 403,
      message: "Import reserve aux roles Direction et Controle de gestion.",
    };
  }
  if (profil?.demo) {
    return {
      etat: "echec",
      statut: null,
      message:
        "Mode demonstration : il n'y a pas de base a alimenter. Renseigner web/.env.local " +
        "et api/.env, puis se connecter avec un vrai compte.",
    };
  }

  const domaine = donnees.get("domaine");
  const fichier = donnees.get("fichier");

  if (typeof domaine !== "string" || domaine === "") {
    return { etat: "echec", statut: null, message: "Aucun domaine d'import choisi." };
  }
  if (!(fichier instanceof File) || fichier.size === 0) {
    return { etat: "echec", statut: null, message: "Aucun fichier selectionne." };
  }

  // On ne transmet que les champs renseignes : l'API REFUSE un parametre qui ne
  // vaut rien pour le domaine choisi (un `devise` envoye au credit, par exemple),
  // et c'est voulu — un parametre ignore en silence ferait croire a un import
  // qu'on n'a pas fait.
  const corps = new FormData();
  corps.set("fichier", fichier, fichier.name);
  for (const champ of CHAMPS) {
    const valeur = donnees.get(champ);
    if (typeof valeur === "string" && valeur.trim() !== "") corps.set(champ, valeur.trim());
  }

  const reponse = await televerserApi<ResultatImport>(
    `/import/${encodeURIComponent(domaine)}`,
    corps,
    jeton,
  );

  if (!reponse.ok) {
    return { etat: "echec", statut: reponse.statut, message: reponse.erreur };
  }

  // Le socle vient de changer : les ecrans qui en vivent ne doivent pas servir
  // leur version d'avant l'import.
  revalidatePath("/import");
  revalidatePath("/credit");

  return { etat: "succes", resultat: reponse.donnees };
}
