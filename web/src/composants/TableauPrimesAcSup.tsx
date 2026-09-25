/**
 * PopPilot — primes des agents de credit et superviseurs (GET /primes/ac-sup).
 *
 * Une ligne par actif du roster : bases (realise / objectif, encours, epargne,
 * PAR30), taux, type de prime, coefficient PAR, montants et motif. Chiffres de
 * l'API seulement — la regle vit dans engine/moteur_primes.py (validee 31/31).
 */
import { entier, montant, pourcent } from "@/lib/format";
import type { LignePrimeAcSup } from "@/lib/primes";

const th = "whitespace-nowrap px-2.5 py-2 text-right text-[11px] font-semibold uppercase tracking-wide text-pop-gris";
const td = "chiffres whitespace-nowrap px-2.5 py-1.5 text-right text-[12px] text-pop-encre";
const p = (v: number | null | undefined) => (v == null ? "—" : pourcent(v * 100));

export function TableauPrimesAcSup({ titre, lignes, total }: { titre: string; lignes: LignePrimeAcSup[]; total: number }) {
  return (
    <div className="space-y-2">
      <h3 className="text-sm font-semibold text-pop-encre">
        {titre} — total {montant(total)} USD ({entier(lignes.length)})
      </h3>
      <div className="overflow-x-auto rounded-xl border border-pop-bord">
        <table className="min-w-max border-collapse">
          <thead>
            <tr className="border-b border-pop-bord bg-pop-fond">
              <th className={`${th} text-left`}>Nom</th>
              <th className={th}>Produit</th>
              <th className={th}>Volume / objectif</th>
              <th className={th}>% volume</th>
              <th className={th}>Nombre / objectif</th>
              <th className={th}>% nombre</th>
              <th className={th}>Encours</th>
              <th className={th}>Credits</th>
              <th className={th}>Epargne</th>
              <th className={th}>Couverture</th>
              <th className={th}>PAR30</th>
              <th className={th}>Type</th>
              <th className={th}>Coef. PAR</th>
              <th className={th}>Prime credit</th>
              <th className={th}>Prime couverture</th>
              <th className={th}>Prime totale</th>
              <th className={`${th} text-left`}>Motif</th>
            </tr>
          </thead>
          <tbody>
            {lignes.map((l) => (
              <tr key={`${l.agence}-${l.nom}`} className="border-b border-pop-bord/60">
                <td className="whitespace-nowrap px-2.5 py-1.5 text-left text-[12px] font-medium text-pop-encre">
                  {l.nom}
                  <span className="ml-1 text-[11px] font-normal text-pop-gris">({l.agence})</span>
                </td>
                <td className={td}>{l.produit}</td>
                <td className={td}>
                  {montant(l.volume_realise)} / {l.volume_objectif == null ? "—" : montant(l.volume_objectif)}
                </td>
                <td className={td}>{p(l.taux_volume)}</td>
                <td className={td}>
                  {entier(l.nombre_realise)} / {l.nombre_objectif == null ? "—" : entier(l.nombre_objectif)}
                </td>
                <td className={td}>{p(l.taux_nombre)}</td>
                <td className={td}>{montant(l.encours)}</td>
                <td className={td}>{entier(l.nb_credits)}</td>
                <td className={td}>{montant(l.epargne)}</td>
                <td className={td}>{p(l.taux_couverture)}</td>
                <td className={td}>{p(l.par30)}</td>
                <td className={td}>{l.type_prime}</td>
                <td className={td}>{l.coefficient_par.toLocaleString("fr-FR")}</td>
                <td className={td}>{montant(l.prime_credit)}</td>
                <td className={td}>{montant(l.prime_couverture)}</td>
                <td className={`${td} font-semibold`}>{montant(l.prime_totale)}</td>
                <td className="px-2.5 py-1.5 text-left text-[11px] text-pop-gris">{l.motif}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
