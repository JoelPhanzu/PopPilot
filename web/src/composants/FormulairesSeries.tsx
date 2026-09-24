"use client";

/**
 * PopPilot — alimentation des series : import d'historiques Excel, et calcul
 * par les moteurs pour les arretes charges qui n'ont pas encore de point.
 */
import { useActionState } from "react";
import { alimenterSeries, importerSeries } from "@/app/archives/actions";
import type { EtatArchive } from "@/lib/archives";

const INITIAL: EtatArchive = { etat: "vierge" };
const bouton =
  "rounded-lg bg-pop-bleu px-4 py-2 text-sm font-medium text-white hover:bg-pop-bleu-2 disabled:opacity-45";

function Message({ etat }: { etat: EtatArchive }) {
  if (etat.etat === "vierge") return null;
  return (
    <p role="status" className={`text-sm ${etat.etat === "succes" ? "text-pop-ok" : "text-pop-danger"}`}>
      {etat.message}
    </p>
  );
}

export function FormulairesSeries({ nonAlimentes }: { nonAlimentes: string[] }) {
  const [etatImport, importer, importEnCours] = useActionState(importerSeries, INITIAL);
  const [etatCalcul, calculer, calculEnCours] = useActionState(alimenterSeries, INITIAL);

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <form action={calculer} className="space-y-2">
        <h3 className="text-sm font-semibold text-pop-encre">Prolonger avec les moteurs</h3>
        {nonAlimentes.length === 0 ? (
          <p className="text-sm text-pop-gris">Tous les arretes charges sont deja dans les series.</p>
        ) : (
          <>
            <p className="text-sm text-pop-gris">
              Arretes charges sans point calcule : {nonAlimentes.join(", ")}.
            </p>
            {nonAlimentes.map((a) => (
              <input key={a} type="hidden" name="arrete" value={a} />
            ))}
            <button type="submit" disabled={calculEnCours} className={bouton}>
              {calculEnCours ? "Calcul…" : "Calculer et ajouter aux series"}
            </button>
          </>
        )}
        <Message etat={etatCalcul} />
      </form>

      <form action={importer} className="space-y-2">
        <h3 className="text-sm font-semibold text-pop-encre">Importer des historiques</h3>
        <p className="text-sm text-pop-gris">
          Excel, une ligne par point : Indicateur | Date | Agence (vide = consolide) | Valeur |
          Unite. Un point deja calcule par les moteurs n&apos;est pas ecrase.
        </p>
        <div className="flex flex-wrap items-center gap-3">
          <input
            name="fichier"
            type="file"
            required
            accept=".xlsx,.xlsm"
            aria-label="Historique"
            className="text-sm file:mr-3 file:rounded-lg file:border-0 file:bg-pop-fond file:px-3 file:py-1.5"
          />
          <button type="submit" disabled={importEnCours} className={bouton}>
            {importEnCours ? "Import…" : "Importer"}
          </button>
        </div>
        <Message etat={etatImport} />
      </form>
    </div>
  );
}
