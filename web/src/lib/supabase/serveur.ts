import "server-only";

/**
 * PopPilot — client Supabase pour le SERVEUR (composants serveur, actions,
 * route handlers).
 *
 * Un client par requete : jamais de client partage entre deux requetes, sinon
 * la session d'un utilisateur pourrait fuiter vers un autre.
 *
 * Next.js 16 : `cookies()` est asynchrone (les Async Request APIs synchrones
 * ont ete supprimees), d'ou le `await` ci-dessous.
 */
import { cookies } from "next/headers";
import { createServerClient } from "@supabase/ssr";
import type { SupabaseClient } from "@supabase/supabase-js";
import { CLE_ANON_SUPABASE, URL_SUPABASE, supabaseConfigure } from "@/lib/config";

export async function clientServeur(): Promise<SupabaseClient | null> {
  if (!supabaseConfigure()) return null;
  const boite = await cookies();

  return createServerClient(URL_SUPABASE, CLE_ANON_SUPABASE, {
    cookies: {
      getAll() {
        return boite.getAll();
      },
      setAll(aPoser) {
        try {
          for (const { name, value, options } of aPoser) {
            boite.set(name, value, options);
          }
        } catch {
          // Un composant serveur ne peut pas ecrire de cookie : c'est attendu.
          // Le rafraichissement du jeton est assure par src/proxy.ts, qui
          // s'execute avant le rendu et peut, lui, ecrire la reponse.
        }
      },
    },
  });
}
