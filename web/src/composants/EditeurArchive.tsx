"use client";

/**
 * PopPilot — edition en ligne d'une archive tableur.
 *
 * Seules les cellules MODIFIEES partent a l'API, qui les AJOUTE a l'historique
 * (qui, quand) sans toucher au fichier depose. Ajouter une ligne ou une colonne
 * = elargir la grille ; seules les cellules remplies sont enregistrees.
 */
import { useState, useTransition } from "react";
import { enregistrerModifications } from "@/app/archives/actions";
import type { EtatArchive } from "@/lib/archives";

export function EditeurArchive({
  archiveId,
  grille: initiale,
  modifiable,
}: {
  archiveId: number;
  grille: string[][];
  modifiable: boolean;
}) {
  const [grille, setGrille] = useState<string[][]>(() => initiale.map((l) => [...l]));
  const [modifs, setModifs] = useState<Map<string, { ligne: number; colonne: number; valeur: string }>>(new Map());
  const [etat, setEtat] = useState<EtatArchive>({ etat: "vierge" });
  const [enCours, demarrer] = useTransition();
  const largeur = Math.max(1, ...grille.map((l) => l.length));

  function changer(ligne: number, colonne: number, valeur: string) {
    setGrille((g) => g.map((l, i) => (i === ligne ? l.map((c, j) => (j === colonne ? valeur : c)) : l)));
    setModifs((m) => new Map(m).set(`${ligne}:${colonne}`, { ligne, colonne, valeur }));
  }

  function enregistrer() {
    demarrer(async () => {
      const r = await enregistrerModifications(archiveId, [...modifs.values()]);
      setEtat(r);
      if (r.etat === "succes") setModifs(new Map());
    });
  }

  return (
    <div className="space-y-3">
      {modifiable && (
        <div className="flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={() => setGrille((g) => [...g, Array(largeur).fill("")])}
            className="rounded-lg border border-pop-bord bg-pop-carte px-3 py-1.5 text-sm text-pop-encre hover:border-pop-cyan"
          >
            + Ligne
          </button>
          <button
            type="button"
            onClick={() => setGrille((g) => g.map((l) => [...l, ...Array(largeur + 1 - l.length).fill("")]))}
            className="rounded-lg border border-pop-bord bg-pop-carte px-3 py-1.5 text-sm text-pop-encre hover:border-pop-cyan"
          >
            + Colonne
          </button>
          <button
            type="button"
            onClick={enregistrer}
            disabled={enCours || modifs.size === 0}
            className="rounded-lg bg-pop-bleu px-4 py-1.5 text-sm font-medium text-white hover:bg-pop-bleu-2 disabled:opacity-45"
          >
            {enCours ? "Enregistrement…" : `Enregistrer (${modifs.size})`}
          </button>
          {etat.etat !== "vierge" && (
            <span role="status" className={`text-sm ${etat.etat === "succes" ? "text-pop-ok" : "text-pop-danger"}`}>
              {etat.message}
            </span>
          )}
        </div>
      )}
      <div className="max-h-[70vh] overflow-auto rounded-xl border border-pop-bord bg-pop-carte">
        <table className="border-collapse text-[13px]">
          <tbody>
            {grille.map((ligne, i) => (
              <tr key={i}>
                <th className="sticky left-0 border border-pop-bord bg-pop-fond px-2 text-right text-[11px] font-normal text-pop-gris">
                  {i + 1}
                </th>
                {Array.from({ length: largeur }, (_, j) => {
                  const cle = `${i}:${j}`;
                  return (
                    <td key={j} className={`border border-pop-bord p-0 ${modifs.has(cle) ? "bg-pop-alerte/10" : ""}`}>
                      <input
                        value={ligne[j] ?? ""}
                        readOnly={!modifiable}
                        onChange={(e) => changer(i, j, e.target.value)}
                        aria-label={`Ligne ${i + 1}, colonne ${j + 1}`}
                        className="w-36 bg-transparent px-2 py-1 text-pop-encre outline-none focus:bg-white focus:ring-2 focus:ring-pop-cyan/40"
                      />
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
