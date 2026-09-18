/**
 * PopPilot — compte de resultat.
 *
 * Distingue explicitement le RESULTAT COMPTABLE du RESULTAT NET : en cours
 * d'annee ils sont egaux, l'IBP (§67) n'etant du qu'a l'arrete annuel. Les
 * confondre ferait croire que l'impot est deja deduit — et surevaluerait tout
 * ce qui en decoule, ROE et ROA en tete.
 */
import { montant } from "@/lib/format";
import type { EtatsFinanciers } from "@/lib/comptabilite";

export function TableauResultat({
  etats,
  devise = "USD",
}: {
  etats: EtatsFinanciers;
  devise?: string;
}) {
  const { produits, charges, resultat_comptable, resultat_net, resultat_net_cdf, controles } = etats;

  const lignes: { libelle: string; valeur: number; fort?: boolean; note?: string }[] = [
    { libelle: "Produits (classe 7)", valeur: produits },
    { libelle: "Charges (classe 6)", valeur: charges },
    {
      libelle: "Resultat comptable",
      valeur: resultat_comptable,
      fort: true,
      note: "Avant impot sur le benefice.",
    },
    {
      libelle: "Resultat net",
      valeur: resultat_net,
      fort: true,
      note: controles.ibp_deduit
        ? "Apres deduction de l'IBP."
        : "IBP non deduit : il n'est du qu'a l'arrete annuel (§67).",
    },
  ];

  return (
    <section className="overflow-hidden rounded-xl border border-pop-bord bg-pop-carte shadow-sm">
      <header className="border-b border-pop-bord px-5 py-4">
        <h2 className="text-base font-semibold text-pop-encre">Compte de resultat</h2>
        <p className="mt-0.5 text-[13px] text-pop-gris">Montants en {devise}.</p>
      </header>

      <table className="w-full border-collapse">
        <tbody className="divide-y divide-pop-bord">
          {lignes.map((ligne) => (
            <tr key={ligne.libelle} className="transition hover:bg-pop-fond">
              <th scope="row" className="px-5 py-3 text-left">
                <span
                  className={
                    ligne.fort
                      ? "text-[13px] font-semibold text-pop-encre"
                      : "text-[13px] font-normal text-pop-encre"
                  }
                >
                  {ligne.libelle}
                </span>
                {ligne.note && (
                  <span className="mt-0.5 block text-[12px] font-normal text-pop-gris">
                    {ligne.note}
                  </span>
                )}
              </th>
              <td
                className={
                  ligne.fort
                    ? "chiffres px-5 py-3 text-right text-[14px] font-semibold text-pop-encre"
                    : "chiffres px-5 py-3 text-right text-[13px] text-pop-encre"
                }
              >
                {montant(ligne.valeur)}
              </td>
            </tr>
          ))}

          <tr className="bg-pop-fond">
            <th scope="row" className="px-5 py-3 text-left text-[13px] font-normal text-pop-gris">
              Resultat net en CDF
              <span className="mt-0.5 block text-[12px] text-pop-gris">
                {etats.taux_change === null
                  ? "Aucun taux saisi pour cet arrete : le montant CDF n'est pas derive (jamais de taux fige)."
                  : `Converti au taux de l'arrete : ${montant(etats.taux_change)} CDF/USD.`}
              </span>
            </th>
            <td className="chiffres px-5 py-3 text-right text-[13px] text-pop-encre">
              {resultat_net_cdf === null ? "—" : montant(resultat_net_cdf)}
            </td>
          </tr>
        </tbody>
      </table>
    </section>
  );
}
