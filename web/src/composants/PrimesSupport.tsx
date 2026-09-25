"use client";

/**
 * PopPilot — primes des fonctions support, par agence.
 *
 * Premier calcul SANS effectifs : l'API renvoie les agences et leurs
 * realisations (decaissement vs objectif, epargne / encours, PAR30). On saisit
 * ensuite l'effectif support de chaque agence et on recalcule : total agence =
 * prime unitaire × effectif. Une case vide reste « non saisie » (et le dit),
 * elle ne vaut pas 0 en silence.
 */
import { useActionState } from "react";
import { ExportSections } from "@/composants/ExportSections";
import { calculerSupport } from "@/app/primes/actions";
import { montant, pourcent } from "@/lib/format";
import type { EtatAction, PrimesSupport as Reponse } from "@/lib/primes";

const INITIAL: EtatAction<Reponse> = { etat: "vierge" };

export function PrimesSupport({ arrete }: { arrete: string }) {
  const [etat, agir, enCours] = useActionState(calculerSupport, INITIAL);
  const r = etat.etat === "succes" ? etat.resultat : null;

  const th = "px-3 py-2 text-right text-[12px] font-semibold uppercase tracking-wide text-pop-gris";
  const td = "chiffres px-3 py-2 text-right text-[13px] text-pop-encre";

  return (
    <form action={agir} className="space-y-4">
      <input type="hidden" name="arrete" value={arrete} />
      {r && (
        <ExportSections
          titre="Primes des fonctions support"
          sousTitre={`Periode du ${r.arrete} (taux, PAR30 et couverture en fraction)`}
          nom={`PopPilot_primes_support_${r.arrete}`}
          sections={[{
            colonnes: [
              { libelle: "Agence", cle: "agence" }, { libelle: "Decaisse / objectif", cle: "taux_decaissement" },
              { libelle: "PAR30", cle: "par30" }, { libelle: "Epargne / encours", cle: "couverture" },
              { libelle: "Effectif", cle: "effectif" }, { libelle: "Prime decaissement", cle: "prime_decaissement" },
              { libelle: "Prime epargne", cle: "prime_epargne" }, { libelle: "Prime PAR", cle: "prime_par" },
              { libelle: "Prime unitaire", cle: "prime_unitaire" }, { libelle: "Prime totale agence", cle: "prime_totale_agence" },
            ],
            lignes: [...r.agences, { agence: "TOTAL", prime_totale_agence: r.total }],
          }]}
        />
      )}
      {r && (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[52rem] border-collapse text-sm">
            <thead>
              <tr className="border-b border-pop-bord">
                <th className={`${th} text-left`}>Agence</th>
                <th className={th}>Decaisse / objectif</th>
                <th className={th}>Epargne / encours</th>
                <th className={th}>PAR30</th>
                <th className={th}>Unitaire</th>
                <th className={th}>Effectif</th>
                <th className={th}>Total agence</th>
              </tr>
            </thead>
            <tbody>
              {r.agences.map((l) => (
                <tr key={l.agence} className="border-b border-pop-bord/60">
                  <td className="px-3 py-2 font-medium text-pop-encre">{l.agence}</td>
                  <td className={td}>
                    {l.taux_decaissement === null ? "objectif ?" : pourcent(l.taux_decaissement * 100)}
                    <span className="ml-1 text-pop-gris">(+{l.prime_decaissement} $)</span>
                  </td>
                  <td className={td}>
                    {pourcent(l.couverture * 100)}
                    <span className="ml-1 text-pop-gris">(+{l.prime_epargne} $)</span>
                  </td>
                  <td className={td}>
                    {pourcent(l.par30 * 100)}
                    <span className="ml-1 text-pop-gris">(+{l.prime_par} $)</span>
                  </td>
                  <td className={`${td} font-semibold`}>{l.prime_unitaire} $</td>
                  <td className={td}>
                    <input
                      name={`effectif:${l.agence}`}
                      type="number"
                      min={0}
                      step={1}
                      defaultValue={l.effectif ?? ""}
                      aria-label={`Effectif support ${l.agence}`}
                      className="chiffres w-20 rounded-md border border-pop-bord px-2 py-1 text-right"
                    />
                  </td>
                  <td className={`${td} font-semibold`}>
                    {l.effectif_saisi ? montant(l.prime_totale_agence) : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr>
                <td colSpan={6} className="px-3 py-2 text-right text-sm font-semibold text-pop-encre">
                  Total a payer (effectifs saisis)
                </td>
                <td className={`${td} font-semibold`}>{montant(r.total)}</td>
              </tr>
            </tfoot>
          </table>
        </div>
      )}

      {r && r.alertes.length > 0 && (
        <ul className="list-disc space-y-0.5 pl-5 text-xs text-pop-alerte">
          {r.alertes.map((a) => (
            <li key={a}>{a}</li>
          ))}
        </ul>
      )}
      {etat.etat === "echec" && (
        <p role="alert" className="text-sm text-pop-danger">
          {etat.message}
        </p>
      )}

      <button
        type="submit"
        disabled={enCours}
        className="rounded-lg bg-pop-bleu px-4 py-2 text-sm font-medium text-white transition hover:bg-pop-bleu-2 disabled:opacity-45"
      >
        {enCours ? "Calcul…" : r ? "Recalculer avec ces effectifs" : "Calculer les realisations des agences"}
      </button>
    </form>
  );
}
