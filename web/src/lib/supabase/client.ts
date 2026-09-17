"use client";

/**
 * PopPilot — client Supabase pour le NAVIGATEUR (formulaire de connexion).
 *
 * Utilise la cle anonyme : c'est la seule cle qui a le droit d'exister dans un
 * bundle front. Elle est soumise au RLS (supabase/02_auth_rls.sql), donc elle
 * ne donne acces qu'a ce que les policies autorisent pour l'utilisateur
 * connecte. La cle service_role, elle, ignore le RLS : elle reste cote serveur.
 */
import { createBrowserClient } from "@supabase/ssr";
import type { SupabaseClient } from "@supabase/supabase-js";
import { CLE_ANON_SUPABASE, URL_SUPABASE, supabaseConfigure } from "@/lib/config";

/**
 * Renvoie `null` si Supabase n'est pas configure, au lieu de laisser
 * createBrowserClient lever sur une URL au gabarit : l'ecran de connexion peut
 * alors afficher un message clair plutot qu'un ecran blanc.
 */
export function clientNavigateur(): SupabaseClient | null {
  if (!supabaseConfigure()) return null;
  return createBrowserClient(URL_SUPABASE, CLE_ANON_SUPABASE);
}
