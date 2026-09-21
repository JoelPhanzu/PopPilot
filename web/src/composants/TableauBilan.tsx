/**
 * PopPilot — bilan : actif et passif par rubrique.
 *
 * Les deux cotes sont presentes cote a cote, avec leur total et l'ecart
 * d'equilibre. Cet ecart n'est pas un detail technique a cacher : un bilan qui
 * ne boucle pas invalide tout ce qui en decoule, et doit se voir sur l'ecran
 * ou on lit les chiffres, pas dans un journal.
 */
import { montant, part, pourcent } from "@/lib/format";
import type { Rubriques } from "@/lib/comptabilite";

/** Quelques centimes d'ecart viennent des arrondis ; au-dela, c'est un defaut. */
const TOLERANCE_EQUILIBRE = 1;

function Colonne({
  titre,
  rubriques,
  total,
  ligneFinale,
}: {
  titre: string;
  rubriques: Rubriques;
  total: number;
  /**
   * Ligne ajoutee APRES les rubriques de la balance, et qui compte pourtant
   * dans le total : le resultat de l'exercice au passif. Le moteur l'ajoute a
   * `total_passif` sans en faire une rubrique (il n'en est pas une : il se
   * deduit des classes 6 et 7). Sans elle a l'ecran, la colonne passif
   * affichait un total superieur a la somme de ses lignes — le lecteur
   * cherchait une erreur de bilan la ou il n'y avait qu'une ligne manquante.
   */
  ligneFinale?: { libelle: string; valeur: number; note?: string };
}) {
  const lignes = Object.entries(rubriques).sort((a, b) => b[1] - a[1]);

  return (
    <div className="min-w-0">
      <h3 className="border-b border-pop-bord px-4 py-2.5 text-[12px] font-semibold uppercase tracking-wide text-pop-gris">
        {titre}
      </h3>
      <table className="w-full border-collapse">
        <tbody className="divide-y divide-pop-bord">
          {lignes.map(([rubrique, valeur]) => {
            const poids = part(valeur, total);
            return (
              <tr key={rubrique} className="transition hover:bg-pop-fond">
                <th scope="row" className="px-4 py-2.5 text-left text-[13px] font-normal text-pop-encre">
                  {rubrique}
                </th>
                <td className="chiffres px-2 py-2.5 text-right text-[13px] text-pop-encre">
                  {montant(valeur)}
                </td>
                <td className="chiffres px-4 py-2.5 text-right text-[12px] text-pop-gris">
                  {poids === null ? "" : pourcent(poids)}
                </td>
              </tr>
            );
          })}

          {ligneFinale && (
            <tr className="transition hover:bg-pop-fond">
              <th scope="row" className="px-4 py-2.5 text-left">
                <span className="text-[13px] font-normal text-pop-encre">
                  {ligneFinale.libelle}
                </span>
                {ligneFinale.note && (
                  <span className="mt-0.5 block text-[11px] text-pop-gris">
                    {ligneFinale.note}
                  </span>
                )}
              </th>
              <td className="chiffres px-2 py-2.5 text-right text-[13px] text-pop-encre">
                {montant(ligneFinale.valeur)}
              </td>
              <td className="chiffres px-4 py-2.5 text-right text-[12px] text-pop-gris">
                {(() => {
                  const poids = part(ligneFinale.valeur, total);
                  return poids === null ? "" : pourcent(poids);
                })()}
              </td>
            </tr>
          )}
        </tbody>
        <tfoot className="border-t-2 border-pop-bleu bg-pop-fond">
          <tr>
            <th scope="row" className="px-4 py-2.5 text-left text-[13px] font-semibold text-pop-encre">
              Total {titre.toLowerCase()}
            </th>
            <td className="chiffres px-2 py-2.5 text-right text-[13px] font-semibold text-pop-encre">
              {montant(total)}
            </td>
            <td className="px-4 py-2.5" />
          </tr>
        </tfoot>
      </table>
    </div>
  );
}

export function TableauBilan({
  actif,
  passif,
  totalActif,
  totalPassif,
  ecart,
  resultat,
  devise = "USD",
}: {
  actif: Rubriques;
  passif: Rubriques;
  totalActif: number;
  totalPassif: number;
  ecart: number;
  /** Resultat de l'exercice, affiche au passif : il en fait partie du total. */
  resultat: number;
  devise?: string;
}) {
  const equilibre = Math.abs(ecart) <= TOLERANCE_EQUILIBRE;

  return (
    <section className="overflow-hidden rounded-xl border border-pop-bord bg-pop-carte shadow-sm">
      <header className="flex flex-wrap items-center justify-between gap-2 border-b border-pop-bord px-5 py-4">
        <div>
          <h2 className="text-base font-semibold text-pop-encre">Bilan</h2>
          <p className="mt-0.5 text-[13px] text-pop-gris">
            Montants en {devise}, par rubrique du plan comptable.
          </p>
        </div>
        <p
          className={
            equilibre
              ? "rounded-full bg-pop-ok/10 px-3 py-1 text-[12px] font-medium text-pop-ok"
              : "rounded-full bg-pop-danger/10 px-3 py-1 text-[12px] font-medium text-pop-danger"
          }
        >
          {equilibre ? "Bilan equilibre" : "Bilan desequilibre"} &middot; ecart{" "}
          <span className="chiffres">{montant(ecart)}</span>
        </p>
      </header>

      <div className="grid grid-cols-1 divide-y divide-pop-bord lg:grid-cols-2 lg:divide-x lg:divide-y-0">
        <Colonne titre="Actif" rubriques={actif} total={totalActif} />
        <Colonne
          titre="Passif"
          rubriques={passif}
          total={totalPassif}
          ligneFinale={{
            libelle: "Resultat de l'exercice",
            valeur: resultat,
            note: "Non affecte : il equilibre le passif sans etre une rubrique de la balance.",
          }}
        />
      </div>
    </section>
  );
}
