/**
 * PopPilot — suivi budgetaire, une lecture a la fois.
 *
 * Les lignes sont groupees par SENS (charges, puis produits), chaque groupe
 * portant son propre total. Un total general melangeant charges et produits
 * n'aurait aucun sens budgetaire — et il est donc absent, exprès.
 *
 * L'ecart est colore selon sa LECTURE, pas selon son signe : depenser moins
 * que prevu est favorable, encaisser moins ne l'est pas. Une ligne dont le sens
 * n'est pas renseigne dans le mapping (table editable) ne recoit AUCUNE
 * couleur — un vert affiche a l'envers coute plus cher qu'une case neutre.
 */
import { montant, pourcent } from "@/lib/format";
import {
  LIBELLES_SENS,
  enPourcent,
  grouperParSens,
  tendance,
  totaliser,
  type LigneBudget,
  type Niveau,
} from "@/lib/budget";

function classeEcart(sens: string, ecart: number): string {
  const t = tendance(sens, ecart);
  if (t === "favorable") return "text-pop-ok";
  if (t === "defavorable") return "text-pop-danger";
  return "text-pop-encre";
}

export function TableauBudget({
  lignes,
  niveau,
  devise = "USD",
}: {
  lignes: LigneBudget[];
  niveau: Niveau;
  devise?: string;
}) {
  const groupes = grouperParSens(lignes);
  if (groupes.length === 0) return null;

  const th =
    "px-3 py-2.5 text-right text-[12px] font-semibold uppercase tracking-wide text-white/90";

  return (
    <section className="overflow-hidden rounded-xl border border-pop-bord bg-pop-carte shadow-sm">
      <header className="border-b border-pop-bord px-5 py-4">
        <h2 className="text-base font-semibold text-pop-encre">{niveau.titre}</h2>
        <p className="mt-0.5 text-[13px] text-pop-gris">
          Montants en {devise}, depuis la balance sans retraitement. Chaque groupe a son
          total&nbsp;; charges et produits ne se totalisent pas ensemble.
        </p>
      </header>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[46rem] border-collapse">
          <caption className="sr-only">
            {niveau.titre} par ligne budgetaire : {niveau.question}
          </caption>
          <thead className="bg-pop-bleu">
            <tr>
              <th scope="col" className={`${th} text-left`}>
                Ligne budgetaire
              </th>
              <th scope="col" className={th}>{niveau.intituleBudget}</th>
              <th scope="col" className={th}>{niveau.intituleRealise}</th>
              <th scope="col" className={th}>Ecart</th>
              <th scope="col" className={th}>{niveau.intitulePct}</th>
            </tr>
          </thead>

          {groupes.map(({ sens, lignes: duGroupe }) => {
            const total = totaliser(duGroupe, niveau);
            return (
              <tbody key={sens} className="divide-y divide-pop-bord">
                <tr className="bg-pop-fond">
                  <th
                    scope="colgroup"
                    colSpan={5}
                    className="px-3 py-2 text-left text-[12px] font-semibold uppercase tracking-wide text-pop-bleu-2"
                  >
                    {LIBELLES_SENS[sens] ?? `Sens non renseigne (${sens})`}
                  </th>
                </tr>

                {duGroupe.map((l) => {
                  const budget = Number(l[niveau.champBudget]) || 0;
                  const realise = Number(l[niveau.champRealise]) || 0;
                  const ecart = Number(l[niveau.champEcart]) || 0;
                  const pct = enPourcent(l[niveau.champPct] as number | null);
                  return (
                    <tr key={l.ligne} className="transition hover:bg-pop-fond">
                      <th
                        scope="row"
                        className="px-3 py-2.5 text-left text-[13px] font-normal text-pop-encre"
                      >
                        {l.ligne}
                      </th>
                      <td className="chiffres px-3 py-2.5 text-right text-[13px] text-pop-gris">
                        {montant(budget)}
                      </td>
                      <td className="chiffres px-3 py-2.5 text-right text-[13px] text-pop-encre">
                        {montant(realise)}
                      </td>
                      <td
                        className={`chiffres px-3 py-2.5 text-right text-[13px] ${classeEcart(sens, ecart)}`}
                      >
                        {montant(ecart)}
                      </td>
                      <td className="chiffres px-3 py-2.5 text-right text-[13px] text-pop-encre">
                        {/* Pas de budget sur la ligne : pas de taux. Un « 0 % »
                            laisserait croire a une sous-consommation totale
                            alors que rien n'avait ete prevu. */}
                        {pct === null ? "—" : pourcent(pct)}
                      </td>
                    </tr>
                  );
                })}

                <tr className="border-t-2 border-pop-bleu bg-pop-fond">
                  <th
                    scope="row"
                    className="px-3 py-2.5 text-left text-[13px] font-semibold text-pop-encre"
                  >
                    Total {(LIBELLES_SENS[sens] ?? sens).toLowerCase()}
                  </th>
                  <td className="chiffres px-3 py-2.5 text-right text-[13px] font-semibold text-pop-encre">
                    {montant(total.budget)}
                  </td>
                  <td className="chiffres px-3 py-2.5 text-right text-[13px] font-semibold text-pop-encre">
                    {montant(total.realise)}
                  </td>
                  <td
                    className={`chiffres px-3 py-2.5 text-right text-[13px] font-semibold ${classeEcart(sens, total.ecart)}`}
                  >
                    {montant(total.ecart)}
                  </td>
                  <td className="chiffres px-3 py-2.5 text-right text-[13px] font-semibold text-pop-encre">
                    {total.pct === null ? "—" : pourcent(total.pct)}
                  </td>
                </tr>
              </tbody>
            );
          })}
        </table>
      </div>
    </section>
  );
}
