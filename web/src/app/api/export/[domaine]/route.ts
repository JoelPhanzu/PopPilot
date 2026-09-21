/**
 * PopPilot — telechargement des exports Excel.
 *
 * Ce gestionnaire ne produit AUCUN classeur : il relaie celui que l'API a
 * genere. C'est la meme regle que partout ailleurs — le front affiche et
 * transmet, il ne calcule pas. Un export fabrique ici a partir du JSON deja
 * recu finirait par diverger de l'ecran a la premiere evolution d'un moteur,
 * et c'est precisement le classeur qui circule en reunion.
 *
 * POURQUOI PASSER PAR NEXT plutot que de pointer le navigateur sur l'API :
 * l'API n'est pas joignable depuis l'internet (choix de topologie assume), et
 * le jeton Supabase ne doit jamais etre manipule par du code client. Le fichier
 * traverse donc le serveur Next, qui porte l'authentification.
 *
 * Un gestionnaire de route (et non une action serveur) parce qu'un
 * telechargement doit etre un GET adressable : le navigateur s'en charge, avec
 * sa barre de progression, et le corps binaire n'est pas soumis au plafond des
 * actions serveur.
 */
import { NextResponse, type NextRequest } from "next/server";
import { sessionCourante } from "@/lib/session";
import { aAccesTotal } from "@/lib/roles";
import { recupererFichierApi } from "@/lib/api";

/** Domaines exportables (miroir des endpoints /export/* cote API). */
const DOMAINES = ["credit", "comptabilite", "epargne", "budget"] as const;
type Domaine = (typeof DOMAINES)[number];

/**
 * Domaines reserves aux roles d'institution.
 *
 * Le credit en est absent : il est CLOISONNE et non interdit — un role AGENCE
 * exporte son agence, et l'API recalcule le total sur ses seules lignes.
 */
const RESERVES: ReadonlySet<string> = new Set(["comptabilite", "epargne", "budget"]);

/** Parametres transmis a l'API, par domaine. Tout le reste est ignore. */
const PARAMETRES: Record<Domaine, readonly string[]> = {
  credit: ["arrete"],
  comptabilite: ["arrete"],
  epargne: ["arrete"],
  budget: ["arrete", "precedent", "hypothese"],
};

function estDomaine(valeur: string): valeur is Domaine {
  return (DOMAINES as readonly string[]).includes(valeur);
}

/** Erreur lisible : ce gestionnaire est atteint par un clic, pas par un script. */
function refus(message: string, statut: number) {
  return new NextResponse(message, {
    status: statut,
    headers: { "Content-Type": "text/plain; charset=utf-8" },
  });
}

export async function GET(
  requete: NextRequest,
  contexte: { params: Promise<{ domaine: string }> },
) {
  const { domaine } = await contexte.params;

  if (!estDomaine(domaine)) {
    return refus(
      `Domaine d'export inconnu : ${domaine}. Domaines : ${DOMAINES.join(", ")}.`,
      404,
    );
  }

  const { profil, jeton } = await sessionCourante();
  if (profil === null) return refus("Session expiree : se reconnecter.", 401);
  if (profil.demo) {
    return refus(
      "Mode demonstration : il n'y a rien a exporter. Les donnees affichees sont " +
        "des illustrations, et un classeur telecharge ne doit jamais pouvoir passer " +
        "pour un arrete reel.",
      409,
    );
  }
  // On refuse ICI ce que l'API refuserait de toute facon : cela evite de
  // fabriquer un classeur pour le jeter, et rend la regle lisible cote front.
  if (RESERVES.has(domaine) && !aAccesTotal(profil)) {
    return refus(
      `L'export « ${domaine} » porte sur des agregats d'institution : il est reserve ` +
        "aux roles Direction, Controle de gestion et Audit.",
      403,
    );
  }

  const parametres = new URLSearchParams();
  for (const nom of PARAMETRES[domaine]) {
    const valeur = requete.nextUrl.searchParams.get(nom);
    if (valeur) parametres.set(nom, valeur);
  }

  const r = await recupererFichierApi(`/export/${domaine}?${parametres}`, jeton);
  if (!r.ok) return refus(r.erreur, r.statut ?? 502);

  // Les en-tetes de l'API font foi : c'est elle qui nomme le fichier et declare
  // son type. Les reecrire ici ferait deux sources pour la meme information.
  const entetes = new Headers();
  for (const nom of ["content-type", "content-disposition", "content-length"]) {
    const valeur = r.reponse.headers.get(nom);
    if (valeur) entetes.set(nom, valeur);
  }
  entetes.set("Cache-Control", "no-store");

  return new NextResponse(r.reponse.body, { status: 200, headers: entetes });
}
