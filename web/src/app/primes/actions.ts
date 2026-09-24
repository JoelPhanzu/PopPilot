"use server";

/**
 * PopPilot — actions serveur de l'ecran Primes. Elles TRANSMETTENT a l'API
 * (POST /primes/support, POST /primes/recouvrement) ; aucun montant n'est
 * calcule ici. Le controle de role est refait par prudence : c'est l'API qui
 * protege (ROLES_ACCES_TOTAL).
 */
import { sessionCourante } from "@/lib/session";
import { aAccesTotal } from "@/lib/roles";
import { appelerApiEcriture, televerserApi } from "@/lib/api";
import type {
  EtatAction,
  PrimesRecouvrement,
  PrimesSuperviseursEpargne,
  PrimesSupport,
} from "@/lib/primes";

async function autorise(): Promise<{ jeton: string | null } | { refus: string }> {
  const { profil, jeton } = await sessionCourante();
  if (!aAccesTotal(profil)) return { refus: "Primes reservees aux roles Direction, CDG et Audit." };
  if (profil?.demo) return { refus: "Mode demonstration : les primes se calculent sur la base reelle." };
  return { jeton };
}

export async function calculerSupport(
  _precedent: EtatAction<PrimesSupport>,
  donnees: FormData,
): Promise<EtatAction<PrimesSupport>> {
  const a = await autorise();
  if ("refus" in a) return { etat: "echec", message: a.refus };

  const arrete = String(donnees.get("arrete") ?? "");
  // Champs « effectif:<agence> » ; une case vide = effectif non saisi (et non 0).
  const effectifs: Record<string, number> = {};
  for (const [cle, valeur] of donnees.entries()) {
    if (!cle.startsWith("effectif:") || typeof valeur !== "string" || valeur.trim() === "") continue;
    const n = Number(valeur);
    if (!Number.isInteger(n) || n < 0) {
      return { etat: "echec", message: `Effectif invalide pour ${cle.slice(9)} : ${valeur}` };
    }
    effectifs[cle.slice(9)] = n;
  }

  const r = await appelerApiEcriture<PrimesSupport>(
    "POST",
    "/primes/support",
    { arrete, effectifs },
    a.jeton,
  );
  return r.ok ? { etat: "succes", resultat: r.donnees } : { etat: "echec", message: r.erreur };
}

export async function calculerRecouvrement(
  _precedent: EtatAction<PrimesRecouvrement>,
  donnees: FormData,
): Promise<EtatAction<PrimesRecouvrement>> {
  const a = await autorise();
  if ("refus" in a) return { etat: "echec", message: a.refus };

  const fichier = donnees.get("fichier");
  if (!(fichier instanceof File) || fichier.size === 0) {
    return { etat: "echec", message: "Aucun fichier selectionne." };
  }
  const corps = new FormData();
  corps.set("fichier", fichier, fichier.name);
  const r = await televerserApi<PrimesRecouvrement>("/primes/recouvrement", corps, a.jeton);
  return r.ok ? { etat: "succes", resultat: r.donnees } : { etat: "echec", message: r.erreur };
}

export async function calculerEpargneSuperviseurs(
  _precedent: EtatAction<PrimesSuperviseursEpargne>,
  donnees: FormData,
): Promise<EtatAction<PrimesSuperviseursEpargne>> {
  const a = await autorise();
  if ("refus" in a) return { etat: "echec", message: a.refus };

  const fichier = donnees.get("fichier");
  if (!(fichier instanceof File) || fichier.size === 0) {
    return { etat: "echec", message: "Aucun fichier selectionne." };
  }
  const corps = new FormData();
  corps.set("fichier", fichier, fichier.name);
  const r = await televerserApi<PrimesSuperviseursEpargne>(
    "/primes/superviseurs-epargne",
    corps,
    a.jeton,
  );
  return r.ok ? { etat: "succes", resultat: r.donnees } : { etat: "echec", message: r.erreur };
}
