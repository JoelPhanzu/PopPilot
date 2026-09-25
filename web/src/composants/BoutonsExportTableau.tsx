"use client";

/**
 * PopPilot — exports d'un tableau de bord TEL QU'AFFICHE : CSV, Excel, PDF.
 *
 *  - CSV / Excel / PDF : liens vers /api/export-tableau/{domaine} avec les parametres
 *    de l'ecran (arrete, periode, niveau, filtres) — l'API rappelle les memes
 *    moteurs, le fichier est donc identique a l'ecran. PDF = tableau pagine.
 *  - Imprimer : l'ecran entier (graphiques compris), mise en page d'impression dediee.
 */
import { useSearchParams } from "next/navigation";

const bouton =
  "inline-flex items-center gap-1.5 rounded-lg border border-pop-bord bg-pop-carte px-3 py-1.5 text-[13px] font-medium text-pop-bleu-2 shadow-sm hover:bg-pop-fond";

export function BoutonsExportTableau({
  domaine,
  parametres = {},
}: {
  domaine: "credit" | "epargne" | "clients" | "taux";
  /** Parametres a imposer en plus de ceux de l'URL (ex. l'arrete reellement affiche). */
  parametres?: Record<string, string | undefined>;
}) {
  const url = useSearchParams();
  const lien = (format: string) => {
    const q = new URLSearchParams(url.toString());
    for (const [k, v] of Object.entries(parametres)) {
      if (v) q.set(k, v);
    }
    q.set("format", format);
    return `/api/export-tableau/${domaine}?${q.toString()}`;
  };
  return (
    <div className="flex flex-wrap items-center gap-2 print:hidden">
      <a href={lien("csv")} download className={bouton}>
        <span aria-hidden>↓</span> CSV
      </a>
      <a href={lien("xlsx")} download className={bouton}>
        <span aria-hidden>↓</span> Excel
      </a>
      <a href={lien("pdf")} download className={bouton}>
        <span aria-hidden>↓</span> PDF
      </a>
      <button type="button" onClick={() => window.print()} className={bouton}>
        <span aria-hidden>⎙</span> Imprimer
      </button>
    </div>
  );
}
