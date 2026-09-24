"use client";

/**
 * PopPilot — depot d'un rapport dans la bibliotheque, ou REMPLACEMENT d'une
 * archive (remplaceId) : l'API cree alors la version suivante et garde l'ancienne.
 */
import { useActionState } from "react";
import { deposerArchive } from "@/app/archives/actions";
import type { EtatArchive } from "@/lib/archives";

const INITIAL: EtatArchive = { etat: "vierge" };
const champ =
  "mt-1 w-full rounded-lg border border-pop-bord bg-white px-2.5 py-1.5 text-sm outline-none focus:border-pop-cyan focus:ring-2 focus:ring-pop-cyan/30";

export function FormulaireArchive({
  remplace,
}: {
  remplace?: { id: number; titre: string; type_rapport: string | null; periode: string | null };
}) {
  const [etat, agir, enCours] = useActionState(deposerArchive, INITIAL);
  const prefixe = remplace ? `r${remplace.id}-` : "n-";

  return (
    <form action={agir} className="space-y-3">
      {remplace && <input type="hidden" name="remplace_id" value={remplace.id} />}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <div>
          <label htmlFor={`${prefixe}titre`} className="text-[12px] font-medium text-pop-gris">
            Titre
          </label>
          <input id={`${prefixe}titre`} name="titre" required defaultValue={remplace?.titre} className={champ} />
        </div>
        <div>
          <label htmlFor={`${prefixe}type`} className="text-[12px] font-medium text-pop-gris">
            Type
          </label>
          <input
            id={`${prefixe}type`}
            name="type_rapport"
            list="types-rapport"
            defaultValue={remplace?.type_rapport ?? ""}
            placeholder="FINA, AML, portee, indicateurs…"
            className={champ}
          />
        </div>
        <div>
          <label htmlFor={`${prefixe}periode`} className="text-[12px] font-medium text-pop-gris">
            Periode
          </label>
          <input
            id={`${prefixe}periode`}
            name="periode"
            defaultValue={remplace?.periode ?? ""}
            placeholder="2025, juillet 2026…"
            className={champ}
          />
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <input
          name="fichier"
          type="file"
          required
          accept=".xlsx,.xlsm,.xls,.csv,.pdf,.docx,.pptx"
          aria-label="Fichier"
          className="text-sm file:mr-3 file:rounded-lg file:border-0 file:bg-pop-fond file:px-3 file:py-1.5"
        />
        <button
          type="submit"
          disabled={enCours}
          className="rounded-lg bg-pop-bleu px-4 py-2 text-sm font-medium text-white hover:bg-pop-bleu-2 disabled:opacity-45"
        >
          {enCours ? "Envoi…" : remplace ? "Deposer la nouvelle version" : "Deposer"}
        </button>
      </div>
      {etat.etat !== "vierge" && (
        <p role="status" className={`text-sm ${etat.etat === "succes" ? "text-pop-ok" : "text-pop-danger"}`}>
          {etat.message}
        </p>
      )}
    </form>
  );
}
