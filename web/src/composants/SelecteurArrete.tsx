"use client";

/**
 * PopPilot — selecteur de date d'arrete.
 *
 * UNE seule barre de filtre, au-dessus de tout ce qu'elle gouverne : cartes,
 * graphique et tableau se recalculent ensemble sur le meme arrete. Jamais de
 * filtre a l'interieur d'une carte.
 *
 * L'arrete vit dans l'URL (?arrete=AAAA-MM-JJ) : l'ecran est partageable et
 * rejouable a l'identique — ce qui compte pour un chiffre qu'on discute a
 * plusieurs. Rappel metier : c'est la date d'ARRETE (date comptable) qui fait
 * foi, pas la date d'import (date_snapshot).
 */
import { useRouter, useSearchParams } from "next/navigation";
import { useState, useTransition } from "react";
import { dateArreteValide } from "@/lib/format";

export function SelecteurArrete({ arrete }: { arrete: string }) {
  const router = useRouter();
  const parametres = useSearchParams();
  const [valeur, setValeur] = useState(arrete);
  const [enCours, demarrer] = useTransition();
  // Resynchronisation apres un retour arriere du navigateur : la page passe
  // `key={arrete}`, donc le composant est remonte et l'etat repart de l'URL.
  // Un useEffect qui ferait setState ici provoquerait un rendu en cascade.

  const valide = dateArreteValide(valeur);
  const inchange = valeur === arrete;

  function appliquer() {
    if (!valide || inchange) return;
    const suivants = new URLSearchParams(parametres.toString());
    suivants.set("arrete", valeur);
    demarrer(() => router.push(`?${suivants.toString()}`));
  }

  return (
    <div className="flex flex-wrap items-end gap-3 rounded-xl border border-pop-bord bg-pop-carte px-4 py-3 shadow-sm">
      <div>
        <label htmlFor="arrete" className="block text-[12px] font-medium text-pop-gris">
          Date d&apos;arrete (date comptable)
        </label>
        <input
          id="arrete"
          type="date"
          value={valeur}
          onChange={(e) => setValeur(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") appliquer();
          }}
          className="chiffres mt-1 rounded-lg border border-pop-bord bg-white px-3 py-1.5 text-sm text-pop-encre
                     outline-none focus:border-pop-cyan focus:ring-2 focus:ring-pop-cyan/30"
        />
      </div>

      <button
        type="button"
        onClick={appliquer}
        disabled={!valide || inchange || enCours}
        className="rounded-lg bg-pop-bleu px-4 py-2 text-sm font-medium text-white transition hover:bg-pop-bleu-2
                   focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-pop-cyan
                   disabled:cursor-not-allowed disabled:opacity-45"
      >
        {enCours ? "Chargement…" : "Afficher"}
      </button>

      {!valide && (
        <p className="text-xs text-pop-danger">Format attendu&nbsp;: AAAA-MM-JJ.</p>
      )}
    </div>
  );
}
