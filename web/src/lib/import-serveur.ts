import "server-only";

/**
 * PopPilot — cote SERVEUR du domaine import : les appels a l'API.
 *
 * Separe de `@/lib/import` (types et libelles) parce que le formulaire est un
 * composant CLIENT : il a besoin des types, jamais du jeton ni de l'URL de
 * l'API. Meme partage que `lib/supabase/client.ts` et `lib/supabase/serveur.ts`.
 */
import { appelerApi, type Resultat } from "@/lib/api";
import type { CatalogueImport, Journal } from "@/lib/import";

export function chargerCatalogue(jeton: string | null): Promise<Resultat<CatalogueImport>> {
  return appelerApi<CatalogueImport>("/import/domaines", jeton);
}

export function chargerJournal(jeton: string | null, limite = 15): Promise<Resultat<Journal>> {
  return appelerApi<Journal>(`/imports?limite=${limite}`, jeton);
}
