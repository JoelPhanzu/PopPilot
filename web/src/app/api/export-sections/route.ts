/**
 * PopPilot — export generique d'un tableau affiche (CSV, Excel, PDF).
 *
 * Relais pur vers POST /export/sections : l'ecran envoie les lignes BRUTES qu'il a
 * recues de l'API (donc deja cloisonnees pour cet utilisateur) ; l'API n'ecrit que
 * le fichier. Aucune valeur n'est calculee ni ici ni la-bas.
 */
import { NextResponse, type NextRequest } from "next/server";
import { sessionCourante } from "@/lib/session";
import { recupererFichierApi } from "@/lib/api";

function refus(message: string, statut: number) {
  return new NextResponse(message, { status: statut, headers: { "Content-Type": "text/plain; charset=utf-8" } });
}

export async function POST(requete: NextRequest) {
  const { profil, jeton } = await sessionCourante();
  if (profil === null) return refus("Session expiree : se reconnecter.", 401);
  if (profil.demo) {
    return refus("Mode demonstration : rien a exporter (les donnees affichees sont des illustrations).", 409);
  }
  let corps: unknown;
  try {
    corps = await requete.json();
  } catch {
    return refus("Demande d'export illisible.", 400);
  }
  const r = await recupererFichierApi("/export/sections", jeton, corps);
  if (!r.ok) return refus(r.erreur, r.statut ?? 502);

  const entetes = new Headers();
  for (const nom of ["content-type", "content-disposition", "content-length"]) {
    const valeur = r.reponse.headers.get(nom);
    if (valeur) entetes.set(nom, valeur);
  }
  entetes.set("Cache-Control", "no-store");
  return new NextResponse(r.reponse.body, { status: 200, headers: entetes });
}
