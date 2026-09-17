"use server";

/**
 * PopPilot — actions serveur de l'ecran de connexion.
 *
 * `entrerEnDemonstration` ouvre une session d'illustration SANS mot de passe.
 * Elle est donc verrouillee deux fois par `modeDemoAutorise()` : impossible des
 * que Supabase est configure, impossible en production. Toute modification de
 * cette fonction doit conserver ces deux verrous.
 */
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { modeDemoAutorise } from "@/lib/config";
import { COOKIE_DEMO } from "@/lib/demo";
import { estRole } from "@/lib/roles";

export async function entrerEnDemonstration(donnees: FormData) {
  if (!modeDemoAutorise()) {
    throw new Error("Mode demonstration indisponible : Supabase est configure.");
  }
  const role = donnees.get("role");
  if (!estRole(role)) throw new Error("Role de demonstration inconnu.");

  const boite = await cookies();
  boite.set(COOKIE_DEMO, role, {
    httpOnly: true,
    sameSite: "lax",
    path: "/",
    maxAge: 60 * 60 * 8,
  });
  redirect("/credit");
}

export async function quitterDemonstration() {
  const boite = await cookies();
  boite.delete(COOKIE_DEMO);
  redirect("/login");
}
