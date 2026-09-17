"use client";

/**
 * PopPilot — deconnexion.
 *
 * Deux chemins selon l'origine de la session : `signOut()` cote Supabase
 * (revoque le jeton et efface les cookies), ou simple suppression du cookie de
 * demonstration. Dans les deux cas on repart sur /login.
 */
import { useRouter } from "next/navigation";
import { useState } from "react";
import { clientNavigateur } from "@/lib/supabase/client";
import { quitterDemonstration } from "@/app/login/actions";

const STYLE =
  "rounded-lg border border-white/20 px-3 py-1.5 text-xs font-medium text-white/80 transition " +
  "hover:border-pop-cyan hover:text-white focus-visible:outline-2 focus-visible:outline-offset-2 " +
  "focus-visible:outline-pop-cyan disabled:opacity-50";

export function BoutonDeconnexion({ demo }: { demo: boolean }) {
  const router = useRouter();
  const [enCours, setEnCours] = useState(false);

  if (demo) {
    return (
      <form action={quitterDemonstration}>
        <button type="submit" className={STYLE}>
          Quitter la demonstration
        </button>
      </form>
    );
  }

  async function seDeconnecter() {
    setEnCours(true);
    const supabase = clientNavigateur();
    if (supabase) await supabase.auth.signOut();
    router.replace("/login");
    router.refresh();
  }

  return (
    <button type="button" onClick={seDeconnecter} disabled={enCours} className={STYLE}>
      {enCours ? "Deconnexion…" : "Se deconnecter"}
    </button>
  );
}
