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
import { DELAI_API_MS, URL_API } from "@/lib/config";

export type Resultat<T> =
  | { ok: true; donnees: T }
  | { ok: false; statut: number | null; erreur: string };

/**
 * Distingue « l'API n'a pas fini a temps » de « l'API n'est pas la ».
 *
 * Les deux remontaient le meme message, qui disait de lancer l'API. Conseil
 * inutile quand elle tourne et calcule : on envoyait chercher une panne qui
 * n'existait pas, au lieu de parler du delai.
 */
function messageDindisponibilite(e: unknown, chemin: string): string {
  const expire =
    e instanceof Error && (e.name === "TimeoutError" || e.name === "AbortError");
  if (expire) {
    return (
      `L'API n'a pas repondu en ${Math.round(DELAI_API_MS / 1000)} s ` +
      `(${URL_API}${chemin}). Le calcul est peut-etre simplement plus long que ce ` +
      "delai : l'augmenter avec NEXT_PUBLIC_POPPILOT_API_TIMEOUT_MS dans web/.env.local."
    );
  }
  const cause = e instanceof Error ? e.message : String(e);
  return (
    `API injoignable (${URL_API}) : ${cause}. ` +
    "Lancer l'API : cd api && uvicorn main:app --reload"
  );
}

export async function appelerApi<T>(
  chemin: string,
  jeton: string | null,
): Promise<Resultat<T>> {
  if (!jeton) {
    return { ok: false, statut: 401, erreur: "Aucun jeton de session a transmettre a l'API." };
  }

  const url = `${URL_API.replace(/\/+$/, "")}${chemin}`;
  const signal = AbortSignal.timeout(DELAI_API_MS);

  let reponse: Response;
  try {
    reponse = await fetch(url, {
      headers: { Authorization: `Bearer ${jeton}`, Accept: "application/json" },
      cache: "no-store",
      signal,
    });
  } catch (e) {
    return { ok: false, statut: null, erreur: messageDindisponibilite(e, chemin) };
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

/**
 * Envoi d'un fichier a l'API (POST multipart) — import des extractions du CBS.
 *
 * Meme chemin que `appelerApi` : le fichier part du SERVEUR Next, pas du
 * navigateur. L'API reste donc inaccessible depuis l'internet, et le jeton
 * n'est jamais manipule par du code client. Le prix a payer est que l'envoi
 * traverse Next (d'ou `serverActions.bodySizeLimit` dans next.config.ts) ;
 * c'est un choix de TOPOLOGIE, pas un detail : ouvrir l'API au navigateur
 * economiserait un saut mais exposerait l'API elle-meme.
 *
 * Aucun `AbortSignal.timeout` ici, contrairement aux lectures : un inventaire
 * epargne (~170 000 comptes) met une quinzaine de secondes a etre INGERE apres
 * l'envoi. Couper laisserait l'import se terminer cote API pendant que l'ecran
 * annonce un echec — le pire des deux mondes.
 */
export async function televerserApi<T>(
  chemin: string,
  corps: FormData,
  jeton: string | null,
): Promise<Resultat<T>> {
  if (!jeton) {
    return { ok: false, statut: 401, erreur: "Aucun jeton de session a transmettre a l'API." };
  }

  const url = `${URL_API.replace(/\/+$/, "")}${chemin}`;

  let reponse: Response;
  try {
    reponse = await fetch(url, {
      method: "POST",
      // Pas de Content-Type : fetch pose lui-meme la frontiere multipart.
      headers: { Authorization: `Bearer ${jeton}`, Accept: "application/json" },
      body: corps,
      cache: "no-store",
    });
  } catch (e) {
    return { ok: false, statut: null, erreur: messageDindisponibilite(e, chemin) };
  }

  if (!reponse.ok) {
    let detail = `HTTP ${reponse.status}`;
    try {
      const corpsJson = (await reponse.json()) as { detail?: unknown };
      if (typeof corpsJson?.detail === "string") detail = corpsJson.detail;
      // FastAPI renvoie une LISTE de problemes quand la validation echoue.
      else if (Array.isArray(corpsJson?.detail)) {
        detail = corpsJson.detail
          .map((p) => (typeof p === "object" && p !== null && "msg" in p ? String(p.msg) : String(p)))
          .join(" · ");
      }
    } catch {
      /* corps non JSON : on garde le code HTTP */
    }
    return { ok: false, statut: reponse.status, erreur: detail };
  }

  return { ok: true, donnees: (await reponse.json()) as T };
}

/**
 * Ecriture sur l'API (POST / DELETE avec un corps JSON) — parametres saisis a
 * la main depuis la page Configuration.
 *
 * Meme chemin que les lectures : l'appel part du SERVEUR Next, jamais du
 * navigateur. Le jeton n'est donc pas manipule par du code client et l'API
 * reste inaccessible depuis l'internet.
 *
 * Pas de `AbortSignal.timeout` : une ecriture coupee en route laisserait la
 * base dans un etat que l'ecran annoncerait comme un echec — le pire des deux
 * mondes. Ces requetes sont courtes (un UPDATE), contrairement aux lectures qui
 * font calculer les moteurs.
 */
export async function appelerApiEcriture<T>(
  methode: "POST" | "DELETE",
  chemin: string,
  corps: unknown,
  jeton: string | null,
): Promise<Resultat<T>> {
  if (!jeton) {
    return { ok: false, statut: 401, erreur: "Aucun jeton de session a transmettre a l'API." };
  }

  const url = `${URL_API.replace(/\/+$/, "")}${chemin}`;
  const entetes: Record<string, string> = {
    Authorization: `Bearer ${jeton}`,
    Accept: "application/json",
  };
  if (corps !== null && corps !== undefined) entetes["Content-Type"] = "application/json";

  let reponse: Response;
  try {
    reponse = await fetch(url, {
      method: methode,
      headers: entetes,
      body: corps === null || corps === undefined ? undefined : JSON.stringify(corps),
      cache: "no-store",
    });
  } catch (e) {
    return { ok: false, statut: null, erreur: messageDindisponibilite(e, chemin) };
  }

  if (!reponse.ok) {
    let detail = `HTTP ${reponse.status}`;
    try {
      const json = (await reponse.json()) as { detail?: unknown };
      if (typeof json?.detail === "string") detail = json.detail;
      // FastAPI renvoie une LISTE de problemes quand la validation echoue.
      else if (Array.isArray(json?.detail)) {
        detail = json.detail
          .map((p) => (typeof p === "object" && p !== null && "msg" in p ? String(p.msg) : String(p)))
          .join(" · ");
      }
    } catch {
      /* corps non JSON : on garde le code HTTP */
    }
    return { ok: false, statut: reponse.status, erreur: detail };
  }

  // Une reponse sans corps (204) ne doit pas faire echouer l'appel.
  const brut = await reponse.text();
  return { ok: true, donnees: (brut ? JSON.parse(brut) : null) as T };
}

/**
 * Recupere un FICHIER de l'API (export Excel) et le rend tel quel.
 *
 * Contrairement aux autres appels, on ne deserialise rien : le corps est
 * binaire et doit traverser le serveur Next sans etre touche. On renvoie donc
 * la `Response` brute, a charge de l'appelant de la relayer au navigateur avec
 * ses en-tetes (type de contenu, nom de fichier).
 *
 * Pas de `AbortSignal.timeout` court : un export de comptabilite fait tourner
 * les moteurs sur toute la balance. Couper a 30 s produirait un telechargement
 * echoue sur un calcul qui allait aboutir.
 */
export async function recupererFichierApi(
  chemin: string,
  jeton: string | null,
  /** Corps JSON : la requete part alors en POST (export generique /export/sections). */
  corps?: unknown,
): Promise<{ ok: true; reponse: Response } | { ok: false; statut: number | null; erreur: string }> {
  if (!jeton) {
    return { ok: false, statut: 401, erreur: "Aucun jeton de session a transmettre a l'API." };
  }

  const url = `${URL_API.replace(/\/+$/, "")}${chemin}`;
  let reponse: Response;
  try {
    reponse = await fetch(url, corps === undefined
      ? { headers: { Authorization: `Bearer ${jeton}` }, cache: "no-store" }
      : {
          method: "POST",
          headers: { Authorization: `Bearer ${jeton}`, "Content-Type": "application/json" },
          body: JSON.stringify(corps),
          cache: "no-store",
        });
  } catch (e) {
    return { ok: false, statut: null, erreur: messageDindisponibilite(e, chemin) };
  }

  if (!reponse.ok) {
    // L'API repond en JSON quand elle refuse : on en tire le message du moteur,
    // qui dit souvent exactement ce qui manque (arrete non importe -> 404).
    let detail = `HTTP ${reponse.status}`;
    try {
      const corps = (await reponse.json()) as { detail?: unknown };
      if (typeof corps?.detail === "string") detail = corps.detail;
    } catch {
      /* corps non JSON : on garde le code HTTP */
    }
    return { ok: false, statut: reponse.status, erreur: detail };
  }

  return { ok: true, reponse };
}
