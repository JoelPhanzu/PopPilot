/**
 * PopPilot — relais du traitement SAGE (POST /sage/traiter).
 *
 * Relais pur, sur le modele de /api/rapports : le grand livre CBS repart tel
 * quel vers l'API, qui applique engine/traitement_sage au taux journalier de la
 * plateforme et renvoie le .xlsx SAGE. Rien n'est lu ni converti ici.
 *
 * Les en-tetes X-Sage-* (statut, totaux debit/credit, ecart, alertes) sont
 * transmis au navigateur : c'est par eux que l'ecran dit si le fichier est
 * importable en l'etat.
 */
import { NextResponse, type NextRequest } from "next/server";
import { sessionCourante } from "@/lib/session";
import { peutEcrire } from "@/lib/roles";
import { URL_API } from "@/lib/config";

function refus(message: string, statut: number) {
  return new NextResponse(message, {
    status: statut,
    headers: { "Content-Type": "text/plain; charset=utf-8" },
  });
}

export async function POST(requete: NextRequest) {
  const { profil, jeton } = await sessionCourante();
  if (profil === null || !jeton) return refus("Session expiree : se reconnecter.", 401);
  if (profil.demo) {
    return refus("Mode demonstration : le taux journalier se lit dans la base, absente ici.", 409);
  }
  if (!peutEcrire(profil)) {
    return refus("Traitement SAGE reserve aux roles Direction et Controle de gestion.", 403);
  }

  let corps: FormData;
  try {
    corps = await requete.formData();
  } catch (e) {
    return refus(`Envoi illisible : ${e instanceof Error ? e.message : String(e)}.`, 400);
  }

  let reponse: Response;
  try {
    // Pas de delai d'attente : un grand livre mensuel se traite en plusieurs
    // secondes ; couper afficherait un echec sur un traitement qui aboutit.
    reponse = await fetch(`${URL_API.replace(/\/+$/, "")}/sage/traiter`, {
      method: "POST",
      headers: { Authorization: `Bearer ${jeton}` },
      body: corps,
      cache: "no-store",
    });
  } catch (e) {
    return refus(
      `API injoignable (${URL_API}) : ${e instanceof Error ? e.message : String(e)}. ` +
        "Lancer l'API : cd api && uvicorn main:app --reload",
      502,
    );
  }

  if (!reponse.ok) {
    let detail = `HTTP ${reponse.status}`;
    try {
      const json = (await reponse.json()) as { detail?: unknown };
      if (typeof json?.detail === "string") detail = json.detail;
    } catch {
      /* corps non JSON : on garde le code HTTP */
    }
    return refus(detail, reponse.status);
  }

  const entetes = new Headers({ "Cache-Control": "no-store" });
  reponse.headers.forEach((valeur, nom) => {
    const transmis = ["content-type", "content-disposition", "content-length"].includes(nom);
    if (transmis || nom.startsWith("x-sage-")) entetes.set(nom, valeur);
  });
  return new NextResponse(reponse.body, { status: 200, headers: entetes });
}
