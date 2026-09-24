"use server";

/**
 * PopPilot — action serveur d'Eljo Smart : transmet la question a POST /eljo.
 * La reponse (valeur exacte, perimetre, arrete) vient des moteurs via l'API ;
 * rien n'est interprete ni calcule ici.
 */
import { revalidatePath } from "next/cache";
import { sessionCourante } from "@/lib/session";
import { appelerApiEcriture } from "@/lib/api";

export type ReponseEljo = {
  reponse: string;
  valeur: number | null;
  detail?: Record<string, unknown>;
  source?: string;
};

export type EtatEljo =
  | { etat: "vierge" }
  | { etat: "succes"; question: string; resultat: ReponseEljo }
  | { etat: "echec"; message: string };

export async function poserQuestion(_precedent: EtatEljo, donnees: FormData): Promise<EtatEljo> {
  const { profil, jeton } = await sessionCourante();
  if (profil === null) return { etat: "echec", message: "Session expiree : se reconnecter." };
  if (profil.demo) {
    return { etat: "echec", message: "Mode demonstration : Eljo repond avec les donnees reelles uniquement." };
  }
  const question = String(donnees.get("question") ?? "").trim();
  if (question.length < 2) return { etat: "echec", message: "Poser une question." };

  const r = await appelerApiEcriture<ReponseEljo>("POST", "/eljo", { question }, jeton);
  if (!r.ok) return { etat: "echec", message: r.erreur };
  revalidatePath("/eljo");
  return { etat: "succes", question, resultat: r.donnees };
}
