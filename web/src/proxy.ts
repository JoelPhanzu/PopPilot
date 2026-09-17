/**
 * PopPilot — proxy Next.js (ex-« middleware », renomme `proxy` en Next.js 16).
 *
 * Deux roles, dans cet ordre :
 *   1. RAFRAICHIR la session Supabase et reecrire les cookies sur la reponse.
 *      Sans cela, un composant serveur ne peut pas ecrire de cookie et la
 *      session expire silencieusement (deconnexions aleatoires).
 *   2. FERMER LA PORTE : une page protegee demandee sans session repart sur
 *      /login. C'est un garde-fou de navigation, PAS la securite : celle-ci
 *      tient au RLS Supabase et au filtre par agence de l'API.
 */
import { NextResponse, type NextRequest } from "next/server";
import { createServerClient } from "@supabase/ssr";
import { CLE_ANON_SUPABASE, URL_SUPABASE, modeDemoAutorise, supabaseConfigure } from "@/lib/config";
import { COOKIE_DEMO } from "@/lib/demo";

/** Chemins accessibles sans session. */
const PUBLICS = ["/login", "/auth"];

function estPublic(chemin: string): boolean {
  return PUBLICS.some((p) => chemin === p || chemin.startsWith(`${p}/`));
}

function versLogin(requete: NextRequest): NextResponse {
  const url = requete.nextUrl.clone();
  url.pathname = "/login";
  url.search = "";
  // On garde la destination pour y revenir apres connexion.
  if (requete.nextUrl.pathname !== "/") {
    url.searchParams.set("suite", requete.nextUrl.pathname + requete.nextUrl.search);
  }
  return NextResponse.redirect(url);
}

export async function proxy(requete: NextRequest) {
  const chemin = requete.nextUrl.pathname;

  // Supabase pas encore branche : on laisse passer (le mode demonstration prend
  // le relais), sauf a exiger le cookie de demonstration sur les pages privees.
  if (!supabaseConfigure()) {
    if (estPublic(chemin)) return NextResponse.next();
    if (!modeDemoAutorise()) return versLogin(requete);
    return requete.cookies.get(COOKIE_DEMO) ? NextResponse.next() : versLogin(requete);
  }

  let reponse = NextResponse.next({ request: requete });

  const supabase = createServerClient(URL_SUPABASE, CLE_ANON_SUPABASE, {
    cookies: {
      getAll() {
        return requete.cookies.getAll();
      },
      setAll(aPoser, entetes) {
        for (const { name, value } of aPoser) requete.cookies.set(name, value);
        reponse = NextResponse.next({ request: requete });
        for (const { name, value, options } of aPoser) reponse.cookies.set(name, value, options);
        // Entetes anti-cache imposes par @supabase/ssr : une reponse qui pose un
        // cookie de session ne doit JAMAIS etre mise en cache par un CDN, sinon
        // la session d'un utilisateur serait servie a un autre.
        for (const [cle, valeur] of Object.entries(entetes ?? {})) {
          reponse.headers.set(cle, valeur);
        }
      },
    },
  });

  // Appel tot dans la requete : un rafraichissement qui arrive apres l'envoi de
  // la reponse serait perdu.
  const { data, error } = await supabase.auth.getClaims();
  const connecte = !error && Boolean(data?.claims?.sub);

  if (!connecte && !estPublic(chemin)) return versLogin(requete);

  return reponse;
}

export const config = {
  // Tout sauf les fichiers statiques et les images : inutile de reveiller
  // Supabase pour servir un logo.
  matcher: ["/((?!_next/static|_next/image|favicon.ico|.*\.(?:svg|png|jpg|jpeg|gif|webp|ico)$).*)"],
};
