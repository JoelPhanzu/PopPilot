"use client";

/**
 * PopPilot — contexte de session : le role de l'utilisateur, disponible partout
 * dans l'arbre client.
 *
 * Le profil est resolu COTE SERVEUR (src/lib/session.ts, qui lit la table
 * `utilisateur` comme le fait l'API) puis descendu ici. Il n'est jamais devine
 * dans le navigateur : ce contexte transporte une decision deja prise, il n'en
 * prend aucune.
 *
 * Ce que ce contexte garantit : l'interface ne MONTRE ni ne DEMANDE ce que le
 * role n'a pas le droit de voir. Ce qu'il ne garantit pas : la protection de la
 * donnee elle-meme — assuree par le RLS Supabase et le filtre par agence de
 * l'API (api/auth_supabase.py). Un front se contourne ; ces deux-la, non.
 */
import { createContext, useContext, type ReactNode } from "react";
import {
  aAccesTotal,
  peutEcrire,
  porteeAffichee,
  type Profil,
  type Role,
} from "@/lib/roles";

type ValeurSession = {
  profil: Profil | null;
  /** Vrai pour DIRECTION, CDG, AUDIT : voit toute l'institution. */
  accesTotal: boolean;
  /** Vrai pour DIRECTION, CDG : peut importer / modifier. */
  ecriture: boolean;
  /** Agence de rattachement (role AGENCE), sinon null. */
  agence: string | null;
  /** Ce que couvre un total affiche : « MICROPOP (toutes agences) » ou l'agence. */
  portee: string;
};

const Contexte = createContext<ValeurSession | null>(null);

export function FournisseurSession({
  profil,
  children,
}: {
  profil: Profil | null;
  children: ReactNode;
}) {
  const valeur: ValeurSession = {
    profil,
    accesTotal: aAccesTotal(profil),
    ecriture: peutEcrire(profil),
    agence: profil?.agence ?? null,
    portee: porteeAffichee(profil),
  };
  return <Contexte.Provider value={valeur}>{children}</Contexte.Provider>;
}

export function useSession(): ValeurSession {
  const valeur = useContext(Contexte);
  if (valeur === null) {
    throw new Error("useSession() doit etre appele sous <FournisseurSession>.");
  }
  return valeur;
}

/** N'affiche ses enfants que pour les roles listes. */
export function SiRole({
  roles,
  children,
  sinon = null,
}: {
  roles: readonly Role[];
  children: ReactNode;
  sinon?: ReactNode;
}) {
  const { profil } = useSession();
  if (profil && roles.includes(profil.role)) return <>{children}</>;
  return <>{sinon}</>;
}

/**
 * N'affiche ses enfants qu'aux roles qui voient toute l'institution.
 * A utiliser pour tout agregat global : total MICROPOP, comptabilite,
 * indicateurs prudentiels, provisions.
 */
export function SiAccesTotal({
  children,
  sinon = null,
}: {
  children: ReactNode;
  sinon?: ReactNode;
}) {
  const { accesTotal } = useSession();
  return <>{accesTotal ? children : sinon}</>;
}

/** N'affiche ses enfants qu'aux roles autorises a ecrire (import, saisie). */
export function SiEcriture({ children }: { children: ReactNode }) {
  const { ecriture } = useSession();
  return <>{ecriture ? children : null}</>;
}
