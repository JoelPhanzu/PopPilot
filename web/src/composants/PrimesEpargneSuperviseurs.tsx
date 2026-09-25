"use client";

/**
 * PopPilot — primes des superviseurs epargne (fichier Agence | Cible | Realisation | %).
 *
 * Le fichier porte un MOIS (obligatoire) : la collecte est conservee a ce mois.
 * Palier applique a la REALISATION TOTALE (≥ 50 000 → 60 ; ≥ 70 000 → 100 ;
 * ≥ 100 000 → 200 USD) — aucune agence n'atteint seule le premier palier. Les
 * agences sont detaillees sans prime. Aucun montant n'est calcule ici.
 */
import { useActionState } from "react";
import { calculerEpargneSuperviseurs } from "@/app/primes/actions";
import { montant, pourcent } from "@/lib/format";
import type { EtatAction, PrimesSuperviseursEpargne as Reponse } from "@/lib/primes";

const INITIAL: EtatAction<Reponse> = { etat: "vierge" };

export function PrimesEpargneSuperviseurs() {
  const [etat, agir, enCours] = useActionState(calculerEpargneSuperviseurs, INITIAL);
  const r = etat.etat === "succes" ? etat.resultat : null;
  const th = "px-3 py-2 text-right text-[12px] font-semibold uppercase tracking-wide text-pop-gris";
  const td = "chiffres px-3 py-2 text-right text-[13px] text-pop-encre";
  const taux = (t: number | null) => (t === null ? "—" : pourcent(t * 100));

  return (
    <div className="space-y-4">
      <form action={agir} className="flex flex-wrap items-end gap-3">
        <label className="text-xs font-medium text-pop-gris">
          Mois de la collecte
          <input
            name="mois"
            type="month"
            required
            className="chiffres mt-1 block rounded-lg border border-pop-bord bg-white px-3 py-1.5 text-sm text-pop-encre"
          />
        </label>
        <input
          name="fichier"
          type="file"
          required
          accept=".xlsx,.xlsm"
          aria-label="Tableau epargne des superviseurs"
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
          <p className="text-xs text-pop-gris">
            Collecte de {r.mois} enregistree ({r.fichier}). Bareme : {r.paliers}.
          </p>
          {r.alertes.length > 0 && (
            <ul className="list-disc pl-5 text-xs text-pop-alerte">
              {r.alertes.map((a) => (
                <li key={a}>{a}</li>
              ))}
            </ul>
          )}
          <div className="overflow-x-auto">
            <table className="w-full min-w-[30rem] border-collapse text-sm">
              <thead>
                <tr className="border-b border-pop-bord">
                  <th className={`${th} text-left`}>Agence</th>
                  <th className={th}>Cible</th>
                  <th className={th}>Realisation</th>
                  <th className={th}>%</th>
                </tr>
              </thead>
              <tbody>
                {r.agences.map((l) => (
                  <tr key={l.agence} className="border-b border-pop-bord/60">
                    <td className="px-3 py-2 font-medium text-pop-encre">{l.agence}</td>
                    <td className={td}>{montant(l.cible)}</td>
                    <td className={td}>{montant(l.realisation)}</td>
                    <td className={td}>{taux(l.taux)}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="border-t border-pop-bord">
                  <td className="px-3 py-2 font-semibold text-pop-encre">Total</td>
                  <td className={td}>{montant(r.total.cible)}</td>
                  <td className={td}>{montant(r.total.realisation)}</td>
                  <td className={td}>{taux(r.total.taux)}</td>
                </tr>
                <tr>
                  <td colSpan={4} className="px-3 py-2 text-right text-sm font-semibold text-pop-encre">
                    Prime superviseur epargne ({r.mois}) : {montant(r.total.prime)} USD
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
