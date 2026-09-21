"use client";

/**
 * PopPilot — choix du volet budgetaire : charges OU produits, jamais les deux.
 *
 * Ce ne sont pas deux groupes d'un meme tableau, ce sont DEUX SUIVIS. Un total
 * qui additionnerait une charge et un produit ne designerait rien, et le « % de
 * realisation » calcule dessus serait pire encore. La separation est donc dans
 * la navigation, pas seulement dans la mise en page : on ne peut pas afficher
 * les deux a la fois.
 *
 * Le volet vit dans l'URL (?volet=charges|produits), comme l'arrete et le
 * niveau : l'ecran reste partageable et rejouable a l'identique.
 */
import { useRouter, useSearchParams } from "next/navigation";
import { useTransition } from "react";
import { ORDRE_VOLETS, VOLETS, type CleVolet } from "@/lib/budget";

export function SelecteurVoletBudget({
  volet,
  compte,
}: {
  volet: CleVolet;
  /** Nombre de lignes de chaque volet : un volet vide se voit avant d'etre ouvert. */
  compte: Record<CleVolet, number>;
}) {
  const router = useRouter();
  const parametres = useSearchParams();
  const [enCours, demarrer] = useTransition();

  function choisir(cle: CleVolet) {
    if (cle === volet) return;
    const suivants = new URLSearchParams(parametres.toString());
    suivants.set("volet", cle);
    demarrer(() => router.push(`?${suivants.toString()}`));
  }

  return (
    <div role="tablist" aria-label="Volet budgetaire" className="flex flex-wrap gap-2">
      {ORDRE_VOLETS.map((cle) => {
        const actif = cle === volet;
        return (
          <button
            key={cle}
            type="button"
            role="tab"
            aria-selected={actif}
            disabled={enCours}
            onClick={() => choisir(cle)}
            className={
              actif
                ? "rounded-lg border-b-[3px] border-pop-cyan bg-pop-carte px-5 py-2.5 text-sm font-semibold text-pop-encre shadow-sm"
                : "rounded-lg border-b-[3px] border-transparent px-5 py-2.5 text-sm text-pop-gris transition hover:bg-pop-carte hover:text-pop-encre"
            }
          >
            {VOLETS[cle].onglet}
            <span className="chiffres ml-2 text-[11px] font-normal text-pop-gris">
              {compte[cle]}
            </span>
          </button>
        );
      })}
    </div>
  );
}
