/**
 * PopPilot — PAR30 par agence (barres horizontales).
 *
 * Choix de forme et de couleur (methode dataviz) :
 *  - UNE SEULE serie : la longueur code le montant du PAR30. Pas de second axe,
 *    pas de seconde couleur — le taux en % est un LIBELLE, pas un encodage.
 *  - Les bleus de la charte (#0B3D5C / #1B5E86) sont trop voisins pour servir de
 *    palette categorielle (ecart normal 11,7 < 15 au validateur de palette) :
 *    d'ou une serie unique en #1B5E86, franchement contrastee sur le blanc. Le
 *    cyan #00AEEA (2,48:1) ne porte jamais de donnee.
 *  - Marques fines (14 px), extremite arrondie de 4 px cote valeur, base carree
 *    a l'origine ; graduations en filets PLEINS d'un ton au-dessus du fond.
 *  - Une agence = une entite : aucune barre ne change de couleur selon son rang.
 *  - Survol ET focus clavier donnent le detail ; la valeur reste lisible sans
 *    survol grace a l'etiquette de bout, et le tableau qui suit est la vue
 *    texte equivalente — rien n'est accessible par la seule couleur.
 *
 * Geometrie : l'echelle n'occupe que FACTEUR % de la piste, le reste etant la
 * lane reservee aux etiquettes de bout. Barres ET graduations partagent ce
 * facteur, donc l'axe reste juste et aucune etiquette n'est rognee.
 */
import { montant, montantCompact, pourcent, part } from "@/lib/format";
import type { LigneAgence } from "@/lib/credit";

/** Part de la piste occupee par l'echelle ; le reste accueille les etiquettes. */
const FACTEUR = 72;
/** Largeur de la colonne des noms d'agence + l'ecart, en rem (a partir de sm). */
const DECALAGE = "11.75rem";

/**
 * Graduations sur des nombres ronds (1 / 2 / 2,5 / 5 × 10^n).
 *
 * La derniere graduation COUVRE toujours le maximum (arrondi au pas superieur).
 * Sans cet arrondi, une serie dont le maximum tombe entre deux graduations
 * donnerait une echelle plus courte que la plus grande valeur : la barre la
 * plus longue depassait sa piste (103 % au lieu de 100 %) et l'axe mentait.
 */
function graduations(maximum: number): number[] {
  if (!Number.isFinite(maximum) || maximum <= 0) return [0];
  const brut = maximum / 4;
  const puissance = 10 ** Math.floor(Math.log10(brut));
  const pas =
    [1, 2, 2.5, 5, 10].map((m) => m * puissance).find((p) => p >= brut) ?? puissance * 10;
  const nombre = Math.ceil(maximum / pas);
  // Indices entiers plutot qu'une addition repetee : pas de derive flottante.
  return Array.from({ length: nombre + 1 }, (_, i) => i * pas);
}

export function GraphiquePar({ lignes }: { lignes: LigneAgence[] }) {
  // Une barre unique n'est pas un graphique : les cartes d'indicateurs disent
  // deja le chiffre. On ne dessine qu'a partir de deux agences.
  if (lignes.length < 2) return null;

  const triees = [...lignes].sort((a, b) => b.par30 - a.par30);
  const maximum = Math.max(...triees.map((l) => l.par30));
  const ticks = graduations(maximum);
  const echelle = ticks[ticks.length - 1] || 1;
  const position = (valeur: number) => `${(valeur / echelle) * FACTEUR}%`;

  return (
    <section className="rounded-xl border border-pop-bord bg-pop-carte p-5 shadow-sm">
      <header>
        <h2 className="text-base font-semibold text-pop-encre">PAR30 par agence</h2>
        <p className="mt-0.5 text-[13px] text-pop-gris">
          Montant du portefeuille a risque au-dela de 30 jours, en USD. Le pourcentage
          est la part de l&apos;encours de l&apos;agence.
        </p>
      </header>

      <div className="relative mt-5">
        {/* Graduations : filets pleins, recessifs, alignes sur les barres. */}
        <div
          aria-hidden
          className="pointer-events-none absolute top-0 bottom-8 right-0 hidden sm:block"
          style={{ left: DECALAGE }}
        >
          {ticks.map((t) => (
            <span
              key={t}
              className="absolute top-0 bottom-0 w-px bg-pop-bord"
              style={{ left: position(t) }}
            />
          ))}
        </div>

        <ul className="relative space-y-2">
          {triees.map((ligne) => {
            const taux = ligne.pct_par30 ?? part(ligne.par30, ligne.encours);
            const fermee = (ligne.statut ?? "").toUpperCase() === "FERMEE";

            return (
              <li
                key={ligne.agence}
                tabIndex={0}
                className="group relative flex flex-col gap-1 rounded-lg py-1 outline-none
                           focus-visible:ring-2 focus-visible:ring-pop-cyan/40 sm:flex-row sm:items-center sm:gap-3"
              >
                <span
                  className="shrink-0 truncate text-[13px] text-pop-gris sm:w-44"
                  title={ligne.agence}
                >
                  {ligne.agence}
                  {fermee && (
                    <span className="ml-1.5 text-[10px] uppercase tracking-wide text-pop-alerte">
                      fermee
                    </span>
                  )}
                </span>

                <span className="relative block h-5 min-w-0 flex-1">
                  <span
                    className="absolute top-1/2 left-0 h-3.5 -translate-y-1/2 rounded-r-[4px] bg-pop-bleu-2
                               transition-[filter] group-hover:brightness-110 group-focus:brightness-110"
                    style={{ width: `max(${position(ligne.par30)}, 2px)` }}
                  />
                  {/* Etiquette de bout, dans la lane reservee : jamais rognee. */}
                  <span
                    className="absolute top-1/2 -translate-y-1/2 whitespace-nowrap pl-2 text-[13px]"
                    style={{ left: position(ligne.par30) }}
                  >
                    <span className="chiffres font-medium text-pop-encre">
                      {montantCompact(ligne.par30)}
                    </span>
                    {taux !== null && (
                      <span className="chiffres ml-1.5 hidden text-[12px] text-pop-gris sm:inline">
                        {pourcent(taux)}
                      </span>
                    )}
                  </span>
                </span>

                {/* Detail au survol / au focus : complement, jamais seul acces. */}
                <span
                  role="tooltip"
                  className="pointer-events-none absolute top-full left-0 z-10 hidden w-64 rounded-lg border
                             border-pop-bord bg-pop-carte p-3 text-xs shadow-lg group-hover:block group-focus:block"
                >
                  <span className="block font-semibold text-pop-encre">{ligne.agence}</span>
                  <span className="chiffres mt-1 block text-pop-gris">
                    Encours&nbsp;: {montant(ligne.encours)} USD
                  </span>
                  <span className="chiffres block text-pop-gris">
                    PAR1&nbsp;: {montant(ligne.par1)} USD
                  </span>
                  <span className="chiffres block text-pop-gris">
                    PAR30&nbsp;: {montant(ligne.par30)} USD
                    {taux === null ? "" : ` — ${pourcent(taux)}`}
                  </span>
                </span>
              </li>
            );
          })}
        </ul>

        {/* Axe des valeurs, sous les barres et dans le meme repere. */}
        <div aria-hidden className="relative mt-2 hidden h-6 sm:block">
          <div className="absolute inset-y-0 right-0" style={{ left: DECALAGE }}>
            {ticks.map((t) => (
              <span
                key={t}
                className="chiffres absolute top-0 -translate-x-1/2 text-[11px] text-pop-gris"
                style={{ left: position(t) }}
              >
                {t === 0 ? "0" : montantCompact(t)}
              </span>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
