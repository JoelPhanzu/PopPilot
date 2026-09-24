/**
 * PopPilot — telechargement d'une archive (relais de GET /archives/{id}/fichier).
 *
 * `?modifie=1` rend la version EDITEE en ligne (GET /archives/{id}/export) ; sans
 * ce parametre, le fichier depose, tel quel. Le fichier traverse le serveur Next
 * sans etre lu ni stocke.
 */
import { NextResponse, type NextRequest } from "next/server";
import { sessionCourante } from "@/lib/session";
import { aAccesTotal } from "@/lib/roles";
import { recupererFichierApi } from "@/lib/api";

function refus(message: string, statut: number) {
  return new NextResponse(message, {
    status: statut,
    headers: { "Content-Type": "text/plain; charset=utf-8" },
  });
}

export async function GET(requete: NextRequest, contexte: { params: Promise<{ id: string }> }) {
  const { id } = await contexte.params;
  if (!/^\d+$/.test(id)) return refus("Identifiant d'archive invalide.", 400);

  const { profil, jeton } = await sessionCourante();
  if (profil === null) return refus("Session expiree : se reconnecter.", 401);
  if (!aAccesTotal(profil)) {
    return refus("Archives reservees aux roles Direction, Controle de gestion et Audit.", 403);
  }

  const modifie = requete.nextUrl.searchParams.get("modifie") === "1";
  const r = await recupererFichierApi(`/archives/${id}/${modifie ? "export" : "fichier"}`, jeton);
  if (!r.ok) return refus(r.erreur, r.statut ?? 502);

  const entetes = new Headers({ "Cache-Control": "no-store" });
  for (const nom of ["content-type", "content-disposition", "content-length"]) {
    const valeur = r.reponse.headers.get(nom);
    if (valeur) entetes.set(nom, valeur);
  }
  return new NextResponse(r.reponse.body, { status: 200, headers: entetes });
}
