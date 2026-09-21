"use client";

/**
 * PopPilot — choix de la lecture budgetaire (doctrine figee, Rapport 4).
 *
 * Les trois lectures ne sont pas trois presentations d'un meme chiffre : elles
 * repondent a trois questions differentes. Les empiler dans un seul tableau
 * donnerait douze colonnes de nombres ou personne ne retrouverait laquelle se
 * compare a laquelle. On en montre donc UNE, nommee, avec sa question affichee
 * — et le choix vit dans l'URL, comme l'arrete : l'ecran reste partageable et
 * rejouable a l'identique.
 *
 * Le niveau MENSUEL peut etre indisponible (balance du mois precedent absente).
 * Il est alors desactive plutot que masque : sa disparition silencieuse ferait
 * croire que la plateforme ne sait pas le produire.
 */
import { useRouter, useSearchParams } from "next/navigation";
import { useTransition } from "react";
import { NIVEAUX, ORDRE_NIVEAUX, type CleNiveau } from "@/lib/budget";

export function SelecteurNiveauBudget({
  niveau,
  mensuelDisponible,
  motifMensuelAbsent,
}: {
  niveau: CleNiveau;
  mensuelDisponible: boolean;
  motifMensuelAbsent: string | null;
}) {
  const router = useRouter();
  const parametres = useSearchParams();
  const [enCours, demarrer] = useTransition();

  function choisir(cle: CleNiveau) {
    if (cle === niveau) return;
    const suivants = new URLSearchParams(parametres.toString());
    suivants.set("niveau", cle);
    demarrer(() => router.push(`?${suivants.toString()}`));
  }

  const courant = NIVEAUX[niveau];

  return (
    <div className="rounded-xl border border-pop-bord bg-pop-carte px-4 py-3 shadow-sm">
      <div
        role="tablist"
        aria-label="Lecture budgetaire"
        className="flex flex-wrap gap-1.5"
      >
        {ORDRE_NIVEAUX.map((cle) => {
          const actif = cle === niveau;
          const bloque = cle === "mensuel" && !mensuelDisponible;
          return (
            <button
              key={cle}
              type="button"
              role="tab"
              aria-selected={actif}
              disabled={bloque || enCours}
              title={bloque ? (motifMensuelAbsent ?? undefined) : undefined}
              onClick={() => choisir(cle)}
              className={
                actif
                  ? "rounded-lg bg-pop-bleu px-3.5 py-1.5 text-[13px] font-medium text-white"
                  : "rounded-lg px-3.5 py-1.5 text-[13px] text-pop-gris transition hover:bg-pop-fond hover:text-pop-encre " +
                    "disabled:cursor-not-allowed disabled:text-pop-gris/40 disabled:hover:bg-transparent"
              }
            >
              {NIVEAUX[cle].onglet}
              {bloque && <span className="ml-1.5 text-[10px] uppercase">indisponible</span>}
            </button>
          );
        })}
      </div>

      <p className="mt-2.5 text-[13px] text-pop-encre">{courant.question}</p>
      <p className="mt-0.5 text-[12px] text-pop-gris">{courant.provenance}</p>
    </div>
  );
}
