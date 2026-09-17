import "server-only";

/**
 * PopPilot — identification de l'utilisateur cote serveur.
 *
 * Chaine complete : cookie Supabase → jeton verifie → ligne `utilisateur`
 * (role + agence) → profil. C'est la table `utilisateur` qui fait foi pour le
 * role, exactement comme cote API (auth_supabase.utilisateur_courant) et comme
 * les fonctions pp_role() / pp_agence() du RLS : le role n'est JAMAIS lu dans
 * les metadonnees du jeton, qu'un utilisateur pourrait influencer a
 * l'inscription.
 */
import { cookies } from "next/headers";
import { clientServeur } from "@/lib/supabase/serveur";
import { modeDemoAutorise } from "@/lib/config";
import { estRole, type Profil, type Role } from "@/lib/roles";
import { COOKIE_DEMO, profilDemo } from "@/lib/demo";

export type Session = {
  /** Profil resolu, ou null si personne n'est identifie. */
  profil: Profil | null;
  /** Jeton Supabase a transmettre a l'API FastAPI (Authorization: Bearer …). */
  jeton: string | null;
  /** Renseigne quand un compte est authentifie mais inutilisable (cf. 403 API). */
  avertissement: string | null;
};

const VIDE: Session = { profil: null, jeton: null, avertissement: null };

export async function sessionCourante(): Promise<Session> {
  const supabase = await clientServeur();

  // Supabase non branche : on retombe eventuellement sur le mode demonstration,
  // qui est lui-meme interdit en production (cf. modeDemoAutorise).
  if (supabase === null) {
    if (!modeDemoAutorise()) return VIDE;
    const boite = await cookies();
    const role = boite.get(COOKIE_DEMO)?.value;
    if (!estRole(role)) return VIDE;
    return { profil: profilDemo(role as Role), jeton: null, avertissement: null };
  }

  // getClaims() verifie la signature du jeton (contrairement a une simple
  // lecture du cookie, qui est modifiable par le client).
  const { data: claims, error: erreurClaims } = await supabase.auth.getClaims();
  const uid = claims?.claims?.sub;
  if (erreurClaims || !uid) return VIDE;

  const { data: ligne, error } = await supabase
    .from("utilisateur")
    .select("login, role, agence, actif")
    .eq("auth_uid", uid)
    .eq("actif", true)
    .maybeSingle();

  if (error) {
    return { ...VIDE, avertissement: `Lecture du profil impossible : ${error.message}` };
  }
  if (!ligne || !estRole(ligne.role)) {
    return {
      ...VIDE,
      avertissement:
        "Compte authentifie mais sans profil actif dans la table `utilisateur` " +
        "(colonne auth_uid a rattacher). Voir supabase/03_utilisateurs_test.sql.",
    };
  }

  const { data: donnees } = await supabase.auth.getSession();

  return {
    profil: {
      login: ligne.login as string,
      role: ligne.role as Role,
      agence: (ligne.agence as string | null) ?? null,
      demo: false,
    },
    jeton: donnees.session?.access_token ?? null,
    avertissement: null,
  };
}
