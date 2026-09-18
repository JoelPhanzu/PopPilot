/**
 * PopPilot — les 17 indicateurs prudentiels, groupes par famille.
 *
 * Regle de lecture, et elle est stricte : un indicateur NON CALCULE s'affiche
 * « non calcule » avec son motif, jamais 0 et jamais « conforme ». Le moteur
 * met un point d'honneur a renvoyer `valeur: null` plutot qu'un zero (A2, E6) ;
 * l'ecran doit tenir la meme ligne, sans quoi un ratio jamais calcule
 * passerait pour excellent devant la BCC.
 *
 * Le numerateur et le denominateur restent visibles : un ratio qu'on ne peut
 * pas decomposer ne se discute pas en reunion.
 */
import { entier, montant, pourcent } from "@/lib/format";
import {
  COMPOSITION,
  FAMILLES,
  ordonner,
  verdict,
  type Famille,
  type Indicateur,
  type Indicateurs,
} from "@/lib/comptabilite";

function Pastille({ ind }: { ind: Indicateur }) {
  const v = verdict(ind);
  if (v === null) {
    return (
      <span className="rounded-full bg-pop-bord/60 px-2.5 py-0.5 text-[11px] font-medium text-pop-gris">
        {ind.valeur === null ? "non calcule" : "sans seuil"}
      </span>
    );
  }
  if (v === "conforme") {
    return (
      <span className="rounded-full bg-pop-ok/10 px-2.5 py-0.5 text-[11px] font-medium text-pop-ok">
        conforme
      </span>
    );
  }
  return (
    <span className="rounded-full bg-pop-danger/10 px-2.5 py-0.5 text-[11px] font-medium text-pop-danger">
      hors norme
    </span>
  );
}

/** B2 est un rapport (emprunteurs par agent), les autres des pourcentages. */
function valeurLisible(ind: Indicateur): string {
  if (ind.valeur === null || !Number.isFinite(ind.valeur)) return "—";
  if (ind.sans_pourcent) {
    return new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 1 }).format(ind.valeur);
  }
  return pourcent(ind.valeur);
}

/** Les termes d'un ratio : des effectifs pour B2, des montants ailleurs. */
function terme(valeur: number | null, comptage: boolean): string {
  if (valeur === null || !Number.isFinite(valeur)) return "—";
  return comptage ? entier(valeur) : montant(valeur);
}

export function TableauIndicateurs({ donnees }: { donnees: Indicateurs }) {
  const lignes = ordonner(donnees.indicateurs);
  const familles = [...new Set(lignes.map((l) => l.famille))] as Famille[];

  const th =
    "px-3 py-2.5 text-right text-[12px] font-semibold uppercase tracking-wide text-white/90";

  return (
    <section className="overflow-hidden rounded-xl border border-pop-bord bg-pop-carte shadow-sm">
      <header className="border-b border-pop-bord px-5 py-4">
        <h2 className="text-base font-semibold text-pop-encre">Indicateurs prudentiels</h2>
        <p className="mt-0.5 text-[13px] text-pop-gris">
          Normes BCC. Un indicateur sans valeur est declare non calcule, avec son motif — il
          n&apos;est ni compte comme conforme, ni ramene a zero.
        </p>
      </header>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[56rem] border-collapse">
          <caption className="sr-only">
            Valeur, norme et conformite de chaque indicateur prudentiel
          </caption>
          <thead className="bg-pop-bleu">
            <tr>
              <th scope="col" className={`${th} text-left`}>Indicateur</th>
              <th scope="col" className={th}>Valeur</th>
              <th scope="col" className={th}>Norme</th>
              <th scope="col" className={`${th} text-center`}>Etat</th>
              <th scope="col" className={th}>Numerateur</th>
              <th scope="col" className={th}>Denominateur</th>
            </tr>
          </thead>

          {familles.map((famille) => (
            <tbody key={famille} className="divide-y divide-pop-bord">
              <tr className="bg-pop-fond">
                <th
                  scope="colgroup"
                  colSpan={6}
                  className="px-3 py-2 text-left text-[12px] font-semibold uppercase tracking-wide text-pop-bleu-2"
                >
                  {famille} — {FAMILLES[famille]}
                </th>
              </tr>

              {lignes
                .filter((l) => l.famille === famille)
                .map(({ code, libelle }) => {
                  const ind = donnees.indicateurs[code];
                  const comptage = Boolean(ind.sans_pourcent);
                  return (
                    <tr key={code} className="align-top transition hover:bg-pop-fond">
                      <th scope="row" className="px-3 py-3 text-left">
                        <span className="text-[13px] font-medium text-pop-encre">{libelle}</span>
                        <span className="mt-0.5 block text-[11px] text-pop-gris">
                          {COMPOSITION[code] ?? code}
                        </span>
                        {ind.motif && (
                          <span className="mt-1 block text-[11px] text-pop-alerte">
                            Non calcule&nbsp;: {ind.motif}
                          </span>
                        )}
                        {ind.source && !ind.motif && (
                          <span className="mt-1 block text-[11px] text-pop-gris">
                            Source&nbsp;: {ind.source}
                          </span>
                        )}
                      </th>
                      <td className="chiffres px-3 py-3 text-right text-[14px] font-semibold text-pop-encre">
                        {valeurLisible(ind)}
                      </td>
                      <td className="chiffres px-3 py-3 text-right text-[13px] text-pop-gris">
                        {ind.norme}
                      </td>
                      <td className="px-3 py-3 text-center">
                        <Pastille ind={ind} />
                      </td>
                      <td className="chiffres px-3 py-3 text-right text-[12px] text-pop-gris">
                        {terme(ind.num, comptage)}
                      </td>
                      <td className="chiffres px-3 py-3 text-right text-[12px] text-pop-gris">
                        {terme(ind.den, comptage)}
                      </td>
                    </tr>
                  );
                })}
            </tbody>
          ))}
        </table>
      </div>
    </section>
  );
}
