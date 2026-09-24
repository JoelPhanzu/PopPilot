"use server";

/**
 * PopPilot — actions serveur du module Archives. Elles TRANSMETTENT a l'API
 * (depot, modifications, import de series, calcul par les moteurs) ; c'est
 * l'API qui controle les roles (ROLES_ECRITURE) et trace chaque ecriture.
 */
import { revalidatePath } from "next/cache";
import { sessionCourante } from "@/lib/session";
import { peutEcrire } from "@/lib/roles";
import { appelerApiEcriture, televerserApi } from "@/lib/api";
import type { EtatArchive } from "@/lib/archives";

async function jetonEcriture(): Promise<{ jeton: string | null } | { refus: string }> {
  const { profil, jeton } = await sessionCourante();
  if (!peutEcrire(profil)) return { refus: "Reserve aux roles Direction et Controle de gestion." };
  if (profil?.demo) return { refus: "Mode demonstration : aucune archive a alimenter." };
  return { jeton };
}

export async function deposerArchive(_p: EtatArchive, donnees: FormData): Promise<EtatArchive> {
  const a = await jetonEcriture();
  if ("refus" in a) return { etat: "echec", message: a.refus };
  const fichier = donnees.get("fichier");
  if (!(fichier instanceof File) || fichier.size === 0) {
    return { etat: "echec", message: "Aucun fichier selectionne." };
  }
  const corps = new FormData();
  corps.set("fichier", fichier, fichier.name);
  for (const champ of ["titre", "type_rapport", "periode", "remplace_id"]) {
    const v = donnees.get(champ);
    if (typeof v === "string" && v.trim()) corps.set(champ, v.trim());
  }
  const r = await televerserApi<{ id: number; version: number }>("/archives", corps, a.jeton);
  if (!r.ok) return { etat: "echec", message: r.erreur };
  revalidatePath("/archives");
  return { etat: "succes", message: `Archive enregistree (version ${r.donnees.version}).` };
}

export async function enregistrerModifications(
  archiveId: number,
  modifications: { ligne: number; colonne: number; valeur: string }[],
): Promise<EtatArchive> {
  const a = await jetonEcriture();
  if ("refus" in a) return { etat: "echec", message: a.refus };
  const r = await appelerApiEcriture<{ enregistrees: number }>(
    "POST",
    `/archives/${archiveId}/donnees`,
    { modifications },
    a.jeton,
  );
  if (!r.ok) return { etat: "echec", message: r.erreur };
  revalidatePath(`/archives/${archiveId}`);
  return { etat: "succes", message: `${r.donnees.enregistrees} cellule(s) enregistree(s).` };
}

export async function importerSeries(_p: EtatArchive, donnees: FormData): Promise<EtatArchive> {
  const a = await jetonEcriture();
  if ("refus" in a) return { etat: "echec", message: a.refus };
  const fichier = donnees.get("fichier");
  if (!(fichier instanceof File) || fichier.size === 0) {
    return { etat: "echec", message: "Aucun fichier selectionne." };
  }
  const corps = new FormData();
  corps.set("fichier", fichier, fichier.name);
  const r = await televerserApi<{ acceptees: number; ajout: number; maj: number; garde: number }>(
    "/series/import",
    corps,
    a.jeton,
  );
  if (!r.ok) return { etat: "echec", message: r.erreur };
  revalidatePath("/archives");
  const d = r.donnees;
  return {
    etat: "succes",
    message:
      `${d.acceptees} points : ${d.ajout} ajoutes, ${d.maj} mis a jour` +
      (d.garde ? `, ${d.garde} laisses a la valeur calculee par les moteurs` : "") + ".",
  };
}

export async function alimenterSeries(_p: EtatArchive, donnees: FormData): Promise<EtatArchive> {
  const a = await jetonEcriture();
  if ("refus" in a) return { etat: "echec", message: a.refus };
  const arretes = donnees.getAll("arrete").map(String).filter(Boolean);
  if (arretes.length === 0) return { etat: "echec", message: "Aucun arrete a calculer." };
  let total = 0;
  for (const arrete of arretes) {
    const r = await appelerApiEcriture<{ points: number }>(
      "POST",
      `/series/alimenter?arrete=${encodeURIComponent(arrete)}`,
      null,
      a.jeton,
    );
    if (!r.ok) return { etat: "echec", message: `${arrete} : ${r.erreur}` };
    total += r.donnees.points;
  }
  revalidatePath("/archives");
  return { etat: "succes", message: `${arretes.length} arrete(s) calcule(s), ${total} points.` };
}
