/**
 * PopPilot — detail du PAR par agence (vue tableau du graphique).
 *
 * C'est la vue texte equivalente au graphique : toute valeur dessinee se lit
 * aussi ici, en clair. Les colonnes de chiffres sont en `tabular-nums` pour
 * s'aligner verticalement, et alignees a droite : on compare des montants en
 * balayant une colonne, pas en lisant des phrases.
 *
 * Le PAR90 par agence n'est PAS affiche : GET /par ne le renvoie qu'au niveau
 * global. On prefere une colonne absente a une colonne inventee.
 */
import { entier, montant, pourcent, part } from "@/lib/format";
import type { LigneAgence } from "@/lib/credit";

export function TableauAgences({
  lignes,
  provisions,
}: {
  lignes: LigneAgence[];
  /** Provisions par agence (moteur deriver_provisions), si le role y a droit. */
  provisions?: Record<string, number> | null;
}) {
  if (lignes.length === 0) {
    return (
      <section className="rounded-xl border border-pop-bord bg-pop-carte p-5 shadow-sm">
        <h2 className="text-base font-semibold text-pop-encre">Detail par agence</h2>
        <p className="mt-2 text-sm text-pop-gris">Aucune agence visible pour ce profil.</p>
      </section>
    );
  }

  const triees = [...lignes].sort((a, b) => b.encours - a.encours);
  const avecProvisions = provisions != null && Object.keys(provisions).length > 0;

  // Totaux = somme du detail affiche. Ils ne peuvent donc pas contredire le
  // tableau, ni laisser filtrer le total institution a un role cloisonne.
  const total = triees.reduce(
    (acc, l) => ({
      encours: acc.encours + l.encours,
      par1: acc.par1 + l.par1,
      par30: acc.par30 + l.par30,
      provisions: acc.provisions + (provisions?.[l.agence] ?? 0),
    }),
    { encours: 0, par1: 0, par30: 0, provisions: 0 },
  );

  const th = "px-3 py-2.5 text-right text-[12px] font-semibold uppercase tracking-wide text-white/90";
  const td = "chiffres px-3 py-2.5 text-right text-[13px] text-pop-encre";

  return (
    <section className="overflow-hidden rounded-xl border border-pop-bord bg-pop-carte shadow-sm">
      <header className="border-b border-pop-bord px-5 py-4">
        <h2 className="text-base font-semibold text-pop-encre">Detail par agence</h2>
        <p className="mt-0.5 text-[13px] text-pop-gris">
          Montants en USD. Total = somme des lignes affichees.
        </p>
      </header>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[46rem] border-collapse">
          <caption className="sr-only">
            Encours, PAR1, PAR30 et taux de PAR30 par agence
          </caption>
          <thead className="bg-pop-bleu">
            <tr>
              <th scope="col" className={`${th} text-left`}>Agence</th>
              <th scope="col" className={th}>Encours</th>
              <th scope="col" className={th}>PAR1</th>
              <th scope="col" className={th}>PAR30</th>
              <th scope="col" className={th}>% PAR30</th>
              {avecProvisions && <th scope="col" className={th}>Provisions</th>}
            </tr>
          </thead>
          <tbody className="divide-y divide-pop-bord">
            {triees.map((ligne) => {
              const taux = ligne.pct_par30 ?? part(ligne.par30, ligne.encours);
              const fermee = (ligne.statut ?? "").toUpperCase() === "FERMEE";
              return (
                <tr key={ligne.agence} className="transition hover:bg-pop-fond">
                  <th scope="row" className="px-3 py-2.5 text-left text-[13px] font-medium text-pop-encre">
                    {ligne.agence}
                    {fermee && (
                      <span
                        className="ml-2 rounded-full bg-pop-alerte/10 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-pop-alerte"
                        title="Agence fermee : portefeuille gele, mais reel et declarable"
                      >
                        fermee
                      </span>
                    )}
                  </th>
                  <td className={td}>{montant(ligne.encours)}</td>
                  <td className={td}>{montant(ligne.par1)}</td>
                  <td className={td}>{montant(ligne.par30)}</td>
                  <td className={td}>{pourcent(taux)}</td>
                  {avecProvisions && (
                    <td className={td}>
                      {provisions?.[ligne.agence] === undefined
                        ? "—"
                        : montant(provisions[ligne.agence])}
                    </td>
                  )}
                </tr>
              );
            })}
          </tbody>
          <tfoot className="border-t-2 border-pop-bleu bg-pop-fond">
            <tr>
              <th scope="row" className="px-3 py-2.5 text-left text-[13px] font-semibold text-pop-encre">
                Total ({entier(triees.length)}{" "}
                {triees.length > 1 ? "agences" : "agence"})
              </th>
              <td className={`${td} font-semibold`}>{montant(total.encours)}</td>
              <td className={`${td} font-semibold`}>{montant(total.par1)}</td>
              <td className={`${td} font-semibold`}>{montant(total.par30)}</td>
              <td className={`${td} font-semibold`}>
                {pourcent(part(total.par30, total.encours))}
              </td>
              {avecProvisions && (
                <td className={`${td} font-semibold`}>{montant(total.provisions)}</td>
              )}
            </tr>
          </tfoot>
        </table>
      </div>
    </section>
  );
}
