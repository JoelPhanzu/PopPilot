"use client";

/**
 * PopPilot — exports d'un tableau de bord TEL QU'AFFICHE : CSV, Excel, PDF.
 *
 *  - CSV / Excel : liens vers /api/export-tableau/{domaine} avec les parametres
 *    de l'ecran (arrete, periode, niveau, filtres) — l'API rappelle les memes
 *    moteurs, le fichier est donc identique a l'ecran.
 *  - PDF : impression du navigateur (« Enregistrer au format PDF »), avec une mise
 *    en page dediee (menus et selecteurs masques, paysage). Elle reproduit
 *    exactement ce qu'on regarde, graphiques compris, sans dependance serveur.
 */
import { useSearchParams } from "next/navigation";

const bouton =
  "inline-flex items-center gap-1.5 rounded-lg border border-pop-bord bg-pop-carte px-3 py-1.5 text-[13px] font-medium text-pop-bleu-2 shadow-sm hover:bg-pop-fond";

export function BoutonsExportTableau({
  domaine,
  parametres = {},
}: {
  domaine: "credit" | "epargne" | "clients";
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
      <button type="button" onClick={() => window.print()} className={bouton}>
        <span aria-hidden>⎙</span> PDF
      </button>
    </div>
  );
}
