"use client";

/**
 * PopPilot — boutons CSV / Excel / PDF pour N'IMPORTE QUEL tableau affiche.
 *
 * Les lignes passees sont les donnees BRUTES que l'ecran a recues de l'API (nombres,
 * pas de texte formate) : le fichier est donc identique a l'ecran, et Excel recoit
 * de vrais nombres. Le serveur (POST /export/sections) n'ecrit que le fichier.
 */
import { useState } from "react";

export type ColonneExport = { libelle: string; cle: string };
export type SectionExport = {
  titre?: string;
  colonnes: ColonneExport[];
  lignes: Record<string, unknown>[];
};

const bouton =
  "inline-flex items-center gap-1.5 rounded-lg border border-pop-bord bg-pop-carte px-3 py-1.5 text-[13px] font-medium text-pop-bleu-2 shadow-sm hover:bg-pop-fond disabled:cursor-not-allowed disabled:opacity-50";

export function ExportSections({
  titre,
  sousTitre,
  nom,
  sections,
  imprimer = false,
}: {
  titre: string;
  sousTitre?: string;
  /** Nom du fichier, sans extension (ex. PopPilot_productivite_2026-07-31). */
  nom: string;
  sections: SectionExport[];
  /** Ajoute « Imprimer » : l'ecran tel quel, graphiques compris. */
  imprimer?: boolean;
}) {
  const [enCours, setEnCours] = useState<string | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);

  async function exporter(format: "csv" | "xlsx" | "pdf") {
    setEnCours(format);
    setErreur(null);
    try {
      const r = await fetch("/api/export-sections", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ titre, sous_titre: sousTitre, nom, format, sections }),
      });
      if (!r.ok) {
        setErreur(await r.text());
        return;
      }
      const url = URL.createObjectURL(await r.blob());
      const a = document.createElement("a");
      a.href = url;
      a.download = `${nom}.${format}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch {
      setErreur("Export impossible : le serveur ne repond pas.");
    } finally {
      setEnCours(null);
    }
  }

  const vide = sections.every((s) => s.lignes.length === 0);
  return (
    <div className="flex flex-wrap items-center gap-2 print:hidden">
      {(["csv", "xlsx", "pdf"] as const).map((f) => (
        <button key={f} type="button" disabled={vide || enCours !== null} onClick={() => exporter(f)}
          className={bouton} title={vide ? "Rien a exporter" : undefined}>
          <span aria-hidden>↓</span> {enCours === f ? "…" : f === "xlsx" ? "Excel" : f.toUpperCase()}
        </button>
      ))}
      {imprimer && (
        <button type="button" onClick={() => window.print()} className={bouton}>
          <span aria-hidden>⎙</span> Imprimer
        </button>
      )}
      {erreur && <span role="alert" className="text-xs text-pop-danger">{erreur}</span>}
    </div>
  );
}
