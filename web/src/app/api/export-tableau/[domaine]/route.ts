/**
 * PopPilot — telechargement d'un TABLEAU DE BORD tel qu'affiche (CSV ou Excel).
 *
 * Relais pur, comme /api/export : le fichier est produit par l'API
 * (GET /export/tableau/{domaine}), qui rappelle les endpoints de l'ecran — memes
 * moteurs, meme cloisonnement. Les parametres de l'ecran (arrete, periode,
 * niveau, filtres) sont transmis tels quels, dans la liste blanche du domaine.
 */
import { NextResponse, type NextRequest } from "next/server";
import { sessionCourante } from "@/lib/session";
import { recupererFichierApi } from "@/lib/api";

const PARAMETRES: Record<string, readonly string[]> = {
  credit: ["arrete", "debut", "fin", "precedent", "niveau", "agence", "sexe", "produits", "duree",
    "client", "agent", "superviseur", "format"],
  epargne: ["arrete", "debut", "fin", "niveau", "agence", "devise", "type_depot", "sexe", "groupe", "format"],
  clients: ["arrete", "debut", "fin", "n", "critere", "agence", "sexe", "produits", "duree", "agent",
    "superviseur", "format"],
};

function refus(message: string, statut: number) {
  return new NextResponse(message, { status: statut, headers: { "Content-Type": "text/plain; charset=utf-8" } });
}

export async function GET(requete: NextRequest, contexte: { params: Promise<{ domaine: string }> }) {
  const { domaine } = await contexte.params;
  const permis = PARAMETRES[domaine];
  if (!permis) return refus(`Tableau inconnu : ${domaine}.`, 404);

  const { profil, jeton } = await sessionCourante();
  if (profil === null) return refus("Session expiree : se reconnecter.", 401);
  if (profil.demo) {
    return refus("Mode demonstration : rien a exporter (les donnees affichees sont des illustrations).", 409);
  }

  const parametres = new URLSearchParams();
  for (const nom of permis) {
    for (const valeur of requete.nextUrl.searchParams.getAll(nom)) {
      if (valeur) parametres.append(nom, valeur);
    }
  }
  const r = await recupererFichierApi(`/export/tableau/${domaine}?${parametres}`, jeton);
  if (!r.ok) return refus(r.erreur, r.statut ?? 502);

  const entetes = new Headers();
  for (const nom of ["content-type", "content-disposition", "content-length"]) {
    const valeur = r.reponse.headers.get(nom);
    if (valeur) entetes.set(nom, valeur);
  }
  entetes.set("Cache-Control", "no-store");
  return new NextResponse(r.reponse.body, { status: 200, headers: entetes });
}
