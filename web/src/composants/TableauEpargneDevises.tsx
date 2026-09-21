/**
 * PopPilot — epargne par type ET par devise D'ORIGINE, avec sa contre-valeur USD.
 *
 * DEUX LECTURES, cote a cote, et il ne faut pas les confondre :
 *
 *  - Les colonnes par DEVISE portent les montants tels qu'ils ont ete emis.
 *    Elles ne s'additionnent PAS entre elles : additionner des CDF a des USD
 *    (facteur ~2268) produirait un nombre qui ne designe rien. C'est la meme
 *    discipline que le rapport Systeme de paiement, qui ventile sans convertir.
 *
 *  - La colonne CONTRE-VALEUR USD rend ces montants comparables, en convertissant
 *    le CDF au taux de l'arrete. Elle, elle se totalise — c'est meme sa raison
 *    d'etre, et c'est le seul total general de ce tableau.
 *
 * Le total converti est confronte a `encours_total` du moteur : deux chemins
 * pour le meme nombre. L'ecart s'affiche, et il doit rester nul. Sans taux saisi
 * pour l'arrete, aucune contre-valeur n'est produite — la plateforme ne fige
 * jamais un taux (§42), elle dit ce qui manque.
 */
import { montant, pourcent } from "@/lib/format";
import {
  LIBELLES_TYPE,
  devisesPresentes,
  totalConverti,
  ventilationParDevise,
} from "@/lib/epargne";

/** Au-dela, l'ecart n'est plus de l'arrondi : il se signale. */
const TOLERANCE = 0.01;

export function TableauEpargneDevises({
  parTypeDevise,
  parDeviseOrigine,
  taux,
  encoursTotal,
}: {
  parTypeDevise: Record<string, number>;
  parDeviseOrigine: Record<string, number>;
  /** Taux CDF/USD de l'arrete. `null` : aucune contre-valeur n'est derivee. */
  taux: number | null;
  /** Encours total du moteur, pour confronter le total converti. */
  encoursTotal: number;
}) {
  const devises = devisesPresentes(parDeviseOrigine);
  const lignes = ventilationParDevise(parTypeDevise);
  if (devises.length === 0 || lignes.length === 0) return null;

  const types = [...new Set(lignes.map((l) => l.type))];
  const cellule = new Map(lignes.map((l) => [`${l.type}/${l.devise}`, l.montant]));

  /** Contre-valeur USD d'un type, toutes devises confondues. */
  function converti(type: string): number | null {
    return totalConverti(
      devises
        .map((d) => ({ devise: d, montant: cellule.get(`${type}/${d}`) }))
        .filter((x): x is { devise: string; montant: number } => x.montant !== undefined),
      taux,
    );
  }

  const totalUsd = totalConverti(
    devises.map((d) => ({ devise: d, montant: parDeviseOrigine[d] })),
    taux,
  );
  const ecart = totalUsd === null ? null : totalUsd - encoursTotal;

  const th =
    "px-4 py-2.5 text-right text-[12px] font-semibold uppercase tracking-wide text-white/90";

  return (
    <section className="overflow-hidden rounded-xl border border-pop-bord bg-pop-carte shadow-sm">
      <header className="border-b border-pop-bord px-5 py-4">
        <h2 className="text-base font-semibold text-pop-encre">
          Epargne par devise d&apos;origine
        </h2>
        <p className="mt-0.5 text-[13px] leading-relaxed text-pop-gris">
          Les colonnes par devise portent les montants <strong>tels qu&apos;emis</strong> et ne
          s&apos;additionnent pas entre elles. La derniere colonne donne leur contre-valeur en
          USD
          {taux === null
            ? ", qui ne peut pas etre calculee faute de taux saisi pour cet arrete."
            : `, convertie au taux de l'arrete (${montant(taux)} CDF/USD) — c'est elle qui se totalise.`}
        </p>
      </header>

      <div className="overflow-x-auto">
        <table className="w-full border-collapse">
          <caption className="sr-only">
            Encours epargne par type de depot, par devise d&apos;origine, et contre-valeur USD
          </caption>
          <thead className="bg-pop-bleu">
            <tr>
              <th scope="col" className={`${th} text-left`}>
                Type de depot
              </th>
              {devises.map((d) => (
                <th key={d} scope="col" className={th}>
                  {d}
                </th>
              ))}
              <th scope="col" className={`${th} border-l border-white/25`}>
                Contre-valeur USD
              </th>
              <th scope="col" className={th}>
                Part
              </th>
            </tr>
          </thead>

          <tbody className="divide-y divide-pop-bord">
            {types.map((type) => {
              const usd = converti(type);
              const part =
                usd === null || !encoursTotal ? null : (usd / encoursTotal) * 100;
              return (
                <tr key={type} className="transition hover:bg-pop-fond">
                  <th
                    scope="row"
                    className="px-4 py-2.5 text-left text-[13px] font-normal text-pop-encre"
                  >
                    {LIBELLES_TYPE[type] ?? type}
                  </th>
                  {devises.map((d) => {
                    const v = cellule.get(`${type}/${d}`);
                    return (
                      <td
                        key={d}
                        className="chiffres px-4 py-2.5 text-right text-[13px] text-pop-gris"
                      >
                        {v === undefined ? "" : montant(v)}
                      </td>
                    );
                  })}
                  <td className="chiffres border-l border-pop-bord px-4 py-2.5 text-right text-[13px] font-medium text-pop-encre">
                    {usd === null ? "—" : montant(usd)}
                  </td>
                  <td className="chiffres px-4 py-2.5 text-right text-[12px] text-pop-gris">
                    {part === null ? "—" : pourcent(part)}
                  </td>
                </tr>
              );
            })}
          </tbody>

          <tfoot className="border-t-2 border-pop-bleu bg-pop-fond">
            <tr>
              <th
                scope="row"
                className="px-4 py-2.5 text-left text-[13px] font-semibold text-pop-encre"
              >
                Total
              </th>
              {devises.map((d) => (
                <td
                  key={d}
                  className="chiffres px-4 py-2.5 text-right text-[13px] font-semibold text-pop-encre"
                >
                  {montant(parDeviseOrigine[d])}
                  <span className="ml-1.5 text-[11px] font-normal text-pop-gris">{d}</span>
                </td>
              ))}
              <td className="chiffres border-l border-pop-bord px-4 py-2.5 text-right text-[13px] font-semibold text-pop-encre">
                {totalUsd === null ? "—" : montant(totalUsd)}
                <span className="ml-1.5 text-[11px] font-normal text-pop-gris">USD</span>
              </td>
              <td className="chiffres px-4 py-2.5 text-right text-[12px] text-pop-gris">
                {totalUsd === null ? "—" : pourcent(100)}
              </td>
            </tr>
          </tfoot>
        </table>
      </div>

      {/* Deux chemins pour le meme nombre : la somme des contre-valeurs doit
          retomber sur l'encours total du moteur. On le montre plutot que de le
          supposer. */}
      <p className="border-t border-pop-bord px-5 py-2.5 text-[12px] leading-relaxed text-pop-gris">
        {totalUsd === null ? (
          <>
            Aucun taux n&apos;est saisi pour cet arrete&nbsp;: les contre-valeurs USD ne sont
            pas derivees. Les saisir dans Configuration.
          </>
        ) : ecart !== null && Math.abs(ecart) <= TOLERANCE ? (
          <>
            Contrôle&nbsp;: le total converti retombe exactement sur l&apos;encours du moteur
            (<span className="chiffres">{montant(encoursTotal)}</span> USD).
          </>
        ) : (
          <span className="text-pop-danger">
            Contrôle&nbsp;: le total converti s&apos;ecarte de{" "}
            <span className="chiffres">{montant(ecart)}</span> de l&apos;encours du moteur
            (<span className="chiffres">{montant(encoursTotal)}</span> USD). Une devise
            n&apos;est peut-etre pas convertie de la meme facon des deux cotes.
          </span>
        )}
      </p>
    </section>
  );
}
