/**
 * PopPilot — ventilation de l'epargne par type de depot.
 *
 * Choix de forme (methode dataviz) : UNE seule serie, barres horizontales, la
 * longueur code le montant. Pas de camembert — trois parts de tailles voisines
 * s'y comparent mal, et le CDG a besoin de lire un ecart, pas une impression.
 * Les barres partagent une meme couleur : « a vue », « a terme » et
 * « obligatoire » sont trois categories d'une meme grandeur, pas trois series.
 *
 * Le cyan de la charte (#00AEEA, 2,48:1) ne porte jamais de donnee : la serie
 * est en #1B5E86, franchement contrastee sur le blanc.
 *
 * Les montants dessines sont ceux du bloc HOMOGENE (converti en USD) : ce sont
 * les seuls qui se comparent entre eux. La ventilation par devise d'origine a
 * son propre tableau, ou rien n'est totalise.
 */
import { montant, montantCompact, part, pourcent } from "@/lib/format";
import { COMPOSITION_TYPE, LIBELLES_TYPE, ordonnerTypes } from "@/lib/epargne";

/** Part de la piste occupee par l'echelle ; le reste accueille les etiquettes. */
const FACTEUR = 0.78;

export function VentilationEpargne({
  parType,
  total,
  devise = "USD",
}: {
  parType: Record<string, number>;
  total: number;
  devise?: string;
}) {
  const codes = ordonnerTypes(parType);
  if (codes.length === 0) return null;

  const maxi = Math.max(...codes.map((c) => parType[c] ?? 0), 0);
  if (maxi <= 0) return null;

  return (
    <section className="overflow-hidden rounded-xl border border-pop-bord bg-pop-carte shadow-sm">
      <header className="border-b border-pop-bord px-5 py-4">
        <h2 className="text-base font-semibold text-pop-encre">
          Ventilation par type de depot
        </h2>
        <p className="mt-0.5 text-[13px] text-pop-gris">
          Montants convertis en {devise} au taux de l&apos;arrete&nbsp;: ce sont les seuls
          qui se comparent entre eux.
        </p>
      </header>

      <ul className="divide-y divide-pop-bord">
        {codes.map((code) => {
          const valeur = parType[code] ?? 0;
          const poids = part(valeur, total);
          const largeur = (valeur / maxi) * 100 * FACTEUR;
          return (
            <li key={code} className="px-5 py-3.5 transition hover:bg-pop-fond">
              <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-0.5">
                <span className="text-[13px] font-medium text-pop-encre">
                  {LIBELLES_TYPE[code] ?? code}
                </span>
                <span className="chiffres text-[13px] text-pop-encre">
                  {montant(valeur)}
                  {poids !== null && (
                    <span className="ml-2 text-[12px] text-pop-gris">{pourcent(poids)}</span>
                  )}
                </span>
              </div>

              <div className="mt-2 flex items-center gap-2">
                <div
                  className="h-3.5 shrink-0 rounded-r-[4px] bg-pop-bleu-2"
                  style={{ width: `${largeur}%` }}
                  aria-hidden
                />
                <span className="chiffres text-[11px] text-pop-gris" aria-hidden>
                  {montantCompact(valeur)}
                </span>
              </div>

              {COMPOSITION_TYPE[code] && (
                <p className="mt-1.5 text-[11px] leading-relaxed text-pop-gris">
                  {COMPOSITION_TYPE[code]}
                </p>
              )}
            </li>
          );
        })}
      </ul>

      <p className="border-t border-pop-bord bg-pop-fond px-5 py-2.5 text-[12px] text-pop-gris">
        Total <span className="chiffres">{montant(total)}</span> {devise}
      </p>
    </section>
  );
}
