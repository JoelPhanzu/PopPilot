/**
 * PopPilot — generation d'un rapport reglementaire.
 *
 * Relais pur : les fichiers envoyes par le navigateur repartent tels quels vers
 * l'API, qui appelle les moteurs et renvoie le document rempli. Aucun classeur
 * n'est lu ni fabrique ici — il n'y a qu'un endroit qui sait remplir un gabarit
 * BCC, et c'est `api/engine/`.
 *
 * POURQUOI PASSER PAR NEXT : l'API n'est pas joignable depuis l'internet, et le
 * jeton Supabase ne doit jamais etre manipule par du code client. Le serveur
 * Next porte l'authentification et fait suivre.
 *
 * POURQUOI UN GESTIONNAIRE DE ROUTE et non une action serveur : la reponse est
 * un FICHIER. Une action serveur renvoie des donnees serialisables, pas un flux
 * binaire ; la faire transiter par elle obligerait a l'encoder en base64 et a
 * la reconstruire cote client, pour un document qui peut peser plusieurs Mo.
 *
 * RIEN N'EST CONSERVE : le classeur AML contient brouillards et grand livre,
 * donc des donnees clients. Il traverse ce gestionnaire sans jamais toucher le
 * disque, et l'API detruit sa copie de travail des la reponse envoyee.
 */
import { NextResponse, type NextRequest } from "next/server";
import { sessionCourante } from "@/lib/session";
import { aAccesTotal } from "@/lib/roles";
import { URL_API } from "@/lib/config";

function refus(message: string, statut: number) {
  return new NextResponse(message, {
    status: statut,
    headers: { "Content-Type": "text/plain; charset=utf-8" },
  });
}

export async function POST(
  requete: NextRequest,
  contexte: { params: Promise<{ cle: string }> },
) {
  const { cle } = await contexte.params;

  const { profil, jeton } = await sessionCourante();
  if (profil === null || !jeton) return refus("Session expiree : se reconnecter.", 401);
  if (profil.demo) {
    return refus(
      "Mode demonstration : aucune declaration ne peut etre produite. Un document " +
        "telecharge ici partirait a la banque centrale.",
      409,
    );
  }
  // L'API refuserait de toute facon : on evite d'y envoyer un gabarit de
  // plusieurs Mo pour se faire repondre 403.
  if (!aAccesTotal(profil)) {
    return refus(
      "La generation des rapports reglementaires est reservee aux roles Direction, " +
        "Controle de gestion et Audit.",
      403,
    );
  }

  // Le corps est reconstruit a l'identique : meme champs, memes fichiers. On ne
  // filtre rien — c'est le catalogue de l'API qui decide de ce qu'elle accepte,
  // et elle REFUSE (422) tout parametre hors rapport plutot que de l'ignorer.
  let corps: FormData;
  try {
    corps = await requete.formData();
  } catch (e) {
    return refus(
      `Envoi illisible : ${e instanceof Error ? e.message : String(e)}. ` +
        "Si le fichier est volumineux, verifier proxyClientMaxBodySize dans next.config.ts.",
      400,
    );
  }

  const url = `${URL_API.replace(/\/+$/, "")}/rapports/${encodeURIComponent(cle)}`;
  let reponse: Response;
  try {
    // Aucun delai d'attente : une generation FINA fait tourner les moteurs sur
    // toute la balance. Couper produirait un echec affiche sur un calcul qui
    // allait aboutir.
    reponse = await fetch(url, {
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
    // L'API repond en JSON quand elle refuse : on en tire le message du moteur,
    // qui dit souvent exactement ce qui manque (balance CDF absente, taux non
    // saisi, ventilation F10 incomplete).
    let detail = `HTTP ${reponse.status}`;
    try {
      const json = (await reponse.json()) as { detail?: unknown };
      if (typeof json?.detail === "string") detail = json.detail;
      else if (Array.isArray(json?.detail)) {
        detail = json.detail
          .map((p) =>
            typeof p === "object" && p !== null && "msg" in p ? String(p.msg) : String(p),
          )
          .join(" · ");
      }
    } catch {
      /* corps non JSON : on garde le code HTTP */
    }
    return refus(detail, reponse.status);
  }

  const entetes = new Headers();
  for (const nom of ["content-type", "content-disposition", "content-length"]) {
    const valeur = reponse.headers.get(nom);
    if (valeur) entetes.set(nom, valeur);
  }
  entetes.set("Cache-Control", "no-store");

  return new NextResponse(reponse.body, { status: 200, headers: entetes });
}
