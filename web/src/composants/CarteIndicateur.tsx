/**
 * PopPilot — carte d'indicateur (stat tile).
 *
 * Contrat : intitule sobre, valeur en semi-gras, precision secondaire (la part
 * en pourcentage), note facultative. Les grands nombres restent en chiffres
 * PROPORTIONNELS : `tabular-nums` donne a chaque chiffre la largeur d'un zero
 * et fait paraitre une valeur lache en grande taille — on le reserve aux
 * colonnes qui doivent s'aligner (tableaux, graduations).
 */
import type { ReactNode } from "react";

export function CarteIndicateur({
  intitule,
  valeur,
  precision,
  note,
  vedette = false,
  accent = false,
}: {
  intitule: string;
  valeur: string;
  precision?: string | null;
  note?: ReactNode;
  /** Chiffre phare de la page : un seul par ecran, en grande taille. */
  vedette?: boolean;
  /** Souligne la carte d'un filet cyan (repere, pas un aplat). */
  accent?: boolean;
}) {
  return (
    <article
      className={
        "relative overflow-hidden rounded-xl border border-pop-bord bg-pop-carte p-5 shadow-sm " +
        (vedette ? "sm:col-span-2" : "")
      }
    >
      {accent && <span aria-hidden className="absolute inset-x-0 top-0 h-[3px] bg-pop-cyan" />}
      <h3 className="text-[13px] font-medium text-pop-gris">{intitule}</h3>
      <p
        className={
          "mt-2 font-semibold tracking-tight text-pop-encre " +
          (vedette ? "text-4xl sm:text-5xl" : "text-2xl")
        }
      >
        {valeur}
      </p>
      {precision && <p className="mt-1.5 text-sm text-pop-gris">{precision}</p>}
      {note && <div className="mt-3 text-xs leading-relaxed text-pop-gris">{note}</div>}
    </article>
  );
}
