/**
 * PopPilot — epargne par type ET par devise D'ORIGINE.
 *
 * REGLE ABSOLUE DE CE TABLEAU : aucune somme entre devises. Les montants sont
 * dans leur devise d'emission — additionner des CDF a des USD produirait un
 * nombre qui ne designe rien (facteur ~2268). C'est la meme discipline que le
 * rapport Systeme de paiement, qui ventile par devise SANS convertir, et
 * l'inverse exact de l'AML, qui convertit tout. Confondre les deux a deja
 * coute un total faux (CLAUDE.md, regle « grand livre toujours en USD »).
 *
 * Une colonne par devise, un total PAR COLONNE, et rien en bas a droite : la
 * case ou l'on serait tente d'ecrire un total general reste vide, exprès.
 */
import { montant } from "@/lib/format";
import {
  LIBELLES_TYPE,
  devisesPresentes,
  ventilationParDevise,
} from "@/lib/epargne";

export function TableauEpargneDevises({
  parTypeDevise,
  parDeviseOrigine,
}: {
  parTypeDevise: Record<string, number>;
  parDeviseOrigine: Record<string, number>;
}) {
  const devises = devisesPresentes(parDeviseOrigine);
  const lignes = ventilationParDevise(parTypeDevise);
  if (devises.length === 0 || lignes.length === 0) return null;

  // Une cellule = un couple (type, devise). Un type absent d'une devise laisse
  // la case vide plutot qu'un zero : « ce produit n'existe pas dans cette
  // devise » et « il en existe pour zero » ne se lisent pas pareil.
  const types = [...new Set(lignes.map((l) => l.type))];
  const cellule = new Map(lignes.map((l) => [`${l.type}/${l.devise}`, l.montant]));

  const th = "px-4 py-2.5 text-right text-[12px] font-semibold uppercase tracking-wide text-white/90";

  return (
    <section className="overflow-hidden rounded-xl border border-pop-bord bg-pop-carte shadow-sm">
      <header className="border-b border-pop-bord px-5 py-4">
        <h2 className="text-base font-semibold text-pop-encre">
          Epargne par devise d&apos;origine
        </h2>
        <p className="mt-0.5 text-[13px] text-pop-gris">
          Montants dans leur devise d&apos;emission, <strong>jamais convertis</strong>. Chaque
          colonne a son propre total&nbsp;; il n&apos;y a volontairement pas de total general.
        </p>
      </header>

      <div className="overflow-x-auto">
        <table className="w-full border-collapse">
          <caption className="sr-only">
            Encours epargne par type de depot et par devise d&apos;origine
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
            </tr>
          </thead>

          <tbody className="divide-y divide-pop-bord">
            {types.map((type) => (
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
                      className="chiffres px-4 py-2.5 text-right text-[13px] text-pop-encre"
                    >
                      {v === undefined ? "" : montant(v)}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>

          <tfoot className="border-t-2 border-pop-bleu bg-pop-fond">
            <tr>
              <th
                scope="row"
                className="px-4 py-2.5 text-left text-[13px] font-semibold text-pop-encre"
              >
                Total par devise
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
            </tr>
          </tfoot>
        </table>
      </div>
    </section>
  );
}
