"use client";

/**
 * PopPilot — primes de recouvrement a partir du tableau mensuel
 * (Equipe | Agent | Agence | Montant 91-180 | Montant 181+ | Montant Radie).
 * La ligne TOTAL du fichier sert de controle : un ecart est affiche en alerte.
 */
import { useActionState } from "react";
import { ExportSections } from "@/composants/ExportSections";
import { calculerRecouvrement } from "@/app/primes/actions";
import { montant } from "@/lib/format";
import type { EtatAction, PrimesRecouvrement as Reponse } from "@/lib/primes";

const INITIAL: EtatAction<Reponse> = { etat: "vierge" };

export function PrimesRecouvrement() {
  const [etat, agir, enCours] = useActionState(calculerRecouvrement, INITIAL);
  const r = etat.etat === "succes" ? etat.resultat : null;
  const th = "px-3 py-2 text-right text-[12px] font-semibold uppercase tracking-wide text-pop-gris";
  const td = "chiffres px-3 py-2 text-right text-[13px] text-pop-encre";

  return (
    <div className="space-y-4">
      <form action={agir} className="flex flex-wrap items-end gap-3">
        <input
          name="fichier"
          type="file"
          required
          accept=".xlsx,.xlsm"
          aria-label="Tableau de recouvrement"
          className="text-sm file:mr-3 file:rounded-lg file:border-0 file:bg-pop-fond file:px-3 file:py-1.5"
        />
        <button
          type="submit"
          disabled={enCours}
          className="rounded-lg bg-pop-bleu px-4 py-2 text-sm font-medium text-white hover:bg-pop-bleu-2 disabled:opacity-45"
        >
          {enCours ? "Calcul…" : "Calculer"}
        </button>
      </form>

      {etat.etat === "echec" && (
        <p role="alert" className="text-sm text-pop-danger">
          {etat.message}
        </p>
      )}

      {r && (
        <>
          {r.alertes.length > 0 && (
            <ul className="list-disc pl-5 text-xs text-pop-alerte">
              {r.alertes.map((a) => (
                <li key={a}>{a}</li>
              ))}
            </ul>
          )}
          <ExportSections
            titre="Primes de recouvrement"
            sousTitre={`Fichier ${r.fichier}`}
            nom="PopPilot_primes_recouvrement"
            sections={[
              {
                titre: "Agents",
                colonnes: [
                  { libelle: "Equipe", cle: "equipe" }, { libelle: "Agent", cle: "agent" }, { libelle: "Agence", cle: "agence" },
                  { libelle: "Recouvre 91-180", cle: "m91_180" }, { libelle: "Recouvre 181-360", cle: "m181_360" },
                  { libelle: "Recouvre radie", cle: "radie" }, { libelle: "Prime", cle: "prime" },
                ],
                lignes: [...r.agents, {
                  agent: "TOTAL", m91_180: r.total_recouvre["91-180"], m181_360: r.total_recouvre["181-360"],
                  radie: r.total_recouvre.radie, prime: r.total_primes_agents,
                }],
              },
              {
                titre: "Responsable",
                colonnes: [{ libelle: "Element", cle: "element" }, { libelle: "Montant", cle: "montant" }],
                lignes: [
                  ...Object.entries(r.responsable.detail).map(([element, montant]) => ({ element, montant })),
                  { element: "Prime du responsable", montant: r.responsable.prime },
                ],
              },
            ]}
          />
          <div className="overflow-x-auto">
            <table className="w-full min-w-[44rem] border-collapse text-sm">
              <thead>
                <tr className="border-b border-pop-bord">
                  <th className={`${th} text-left`}>Equipe</th>
                  <th className={`${th} text-left`}>Agent</th>
                  <th className={`${th} text-left`}>Agence</th>
                  <th className={th}>91-180 (1 %)</th>
                  <th className={th}>181-360 (3 %)</th>
                  <th className={th}>Radie (5 %)</th>
                  <th className={th}>Prime</th>
                </tr>
              </thead>
              <tbody>
                {r.agents.map((a, i) => (
                  <tr key={`${a.agent}-${i}`} className="border-b border-pop-bord/60">
                    <td className="px-3 py-2 text-pop-gris">{a.equipe ?? "—"}</td>
                    <td className="px-3 py-2 font-medium text-pop-encre">{a.agent}</td>
                    <td className="px-3 py-2 text-pop-gris">{a.agence ?? "—"}</td>
                    <td className={td}>{montant(a.m91_180)}</td>
                    <td className={td}>{montant(a.m181_360)}</td>
                    <td className={td}>{montant(a.radie)}</td>
                    <td className={`${td} font-semibold`}>{montant(a.prime)}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="border-t border-pop-bord">
                  <td colSpan={3} className="px-3 py-2 font-semibold text-pop-encre">
                    Total agents
                  </td>
                  <td className={td}>{montant(r.total_recouvre["91-180"])}</td>
                  <td className={td}>{montant(r.total_recouvre["181-360"])}</td>
                  <td className={td}>{montant(r.total_recouvre.radie)}</td>
                  <td className={`${td} font-semibold`}>{montant(r.total_primes_agents)}</td>
                </tr>
                <tr>
                  <td colSpan={6} className="px-3 py-2 text-pop-encre">
                    Responsable recouvrement (0,3 % / 0,5 % / 1 % du total recouvre)
                  </td>
                  <td className={`${td} font-semibold`}>{montant(r.responsable.prime)}</td>
                </tr>
              </tfoot>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
