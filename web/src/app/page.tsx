/**
 * PopPilot — point d'entree.
 *
 * Aucune page d'accueil publique : la racine renvoie vers le tableau de bord si
 * une session existe, vers la connexion sinon.
 */
import { redirect } from "next/navigation";
import { sessionCourante } from "@/lib/session";

export const dynamic = "force-dynamic";

export default async function Racine() {
  const { profil } = await sessionCourante();
  redirect(profil === null ? "/login" : "/credit");
}
