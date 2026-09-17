import "server-only";

/**
 * PopPilot — appel de l'API FastAPI qui expose les moteurs valides.
 *
 * L'appel part du SERVEUR Next.js, pas du navigateur : le jeton Supabase n'est
 * jamais manipule par du code client, et l'API n'a pas besoin d'etre ouverte a
 * l'internet — seul le serveur Next doit la joindre (http://localhost:8000 en
 * local, cf. NEXT_PUBLIC_POPPILOT_API).
 *
 * `cache: "no-store"` : un chiffre de pilotage ne se sert jamais tiede. Deux
 * arretes differents doivent donner deux appels.
 */
import { URL_API } from "@/lib/config";

export type Resultat<T> =
  | { ok: true; donnees: T }
  | { ok: false; statut: number | null; erreur: string };

/** Delai au-dela duquel on n'attend plus l'API (elle n'est peut-etre pas lancee). */
const DELAI_MS = 8000;

export async function appelerApi<T>(
  chemin: string,
  jeton: string | null,
): Promise<Resultat<T>> {
  if (!jeton) {
    return { ok: false, statut: 401, erreur: "Aucun jeton de session a transmettre a l'API." };
  }

  const url = `${URL_API.replace(/\/+$/, "")}${chemin}`;
  const signal = AbortSignal.timeout(DELAI_MS);

  let reponse: Response;
  try {
    reponse = await fetch(url, {
      headers: { Authorization: `Bearer ${jeton}`, Accept: "application/json" },
      cache: "no-store",
      signal,
    });
  } catch (e) {
    const cause = e instanceof Error ? e.message : String(e);
    return {
      ok: false,
      statut: null,
      erreur: `API injoignable (${URL_API}) : ${cause}. ` +
        "Lancer l'API : cd api && uvicorn main:app --reload",
    };
  }

  if (!reponse.ok) {
    // FastAPI renvoie {"detail": "..."} — on remonte le message du moteur, qui
    // dit souvent exactement ce qui manque (ex. arrete non importe → 404).
    let detail = `HTTP ${reponse.status}`;
    try {
      const corps = (await reponse.json()) as { detail?: unknown };
      if (typeof corps?.detail === "string") detail = corps.detail;
    } catch {
      /* corps non JSON : on garde le code HTTP */
    }
    return { ok: false, statut: reponse.status, erreur: detail };
  }

  return { ok: true, donnees: (await reponse.json()) as T };
}
