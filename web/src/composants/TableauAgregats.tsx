/**
 * PopPilot — agregats qui alimentent les ratios prudentiels.
 *
 * C'est la table de verification du tableau d'indicateurs : chaque numerateur
 * et chaque denominateur affiche plus haut se retrouve ici, nomme. Un ratio
 * qu'on ne peut pas remonter jusqu'a ses composants ne se defend pas devant
 * la BCC.
 *
 * Deux points de doctrine sont signales a l'ecran, parce qu'ils se perdent
 * sinon dans une liste de nombres :
 *  - les FONDS PROPRES existent en deux versions (decision CDG). La version
 *    HORS RESULTAT pilote TOUS les ratios ; la version resultat affecte est
 *    informative et n'entre jamais dans un ratio. Les afficher sans le dire,
 *    c'est laisser choisir la plus flatteuse.
 *  - certains agregats sont des EFFECTIFS, pas des montants : ni decimales,
 *    ni devise.
 */
import { entier, montant } from "@/lib/format";
import { AGREGATS_COMPTAGE, LIBELLES_AGREGAT } from "@/lib/comptabilite";

/** Agregats informatifs, exclus des ratios : dits comme tels, jamais masques. */
const INFORMATIFS = new Set([
  "fonds_propres_base_avec_resultat",
  "fonds_propres_prudentiels_avec_resultat",
]);

const NOTE_INFORMATIF = "Information seule — n'entre dans aucun ratio (decision CDG).";

export function TableauAgregats({
  agregats,
  devise = "USD",
}: {
  agregats: Record<string, number | null>;
  devise?: string;
}) {
  // Ordre du catalogue d'abord ; tout agregat ajoute cote moteur reste visible
  // en fin de liste, sous son code brut, plutot que d'etre perdu en silence.
  const connus = Object.keys(LIBELLES_AGREGAT).filter((c) => c in agregats);
  const vus = new Set(connus);
  const codes = [...connus, ...Object.keys(agregats).filter((c) => !vus.has(c))];

  if (codes.length === 0) return null;

  return (
    <section className="overflow-hidden rounded-xl border border-pop-bord bg-pop-carte shadow-sm">
      <header className="border-b border-pop-bord px-5 py-4">
        <h2 className="text-base font-semibold text-pop-encre">
          Agregats de calcul
        </h2>
        <p className="mt-0.5 text-[13px] text-pop-gris">
          Les composants des ratios ci-dessus, en {devise}. Chaque numerateur et
          chaque denominateur se retrouve ici.
        </p>
      </header>

      <table className="w-full border-collapse">
        <tbody className="divide-y divide-pop-bord">
          {codes.map((code) => {
            const valeur = agregats[code];
            const comptage = AGREGATS_COMPTAGE.has(code);
            const informatif = INFORMATIFS.has(code);
            return (
              <tr key={code} className="transition hover:bg-pop-fond">
                <th scope="row" className="px-5 py-2.5 text-left">
                  <span className="text-[13px] font-normal text-pop-encre">
                    {LIBELLES_AGREGAT[code] ?? code}
                  </span>
                  {informatif && (
                    <span className="mt-0.5 block text-[11px] text-pop-gris">
                      {NOTE_INFORMATIF}
                    </span>
                  )}
                </th>
                <td
                  className={
                    "chiffres px-5 py-2.5 text-right text-[13px] " +
                    (informatif ? "text-pop-gris" : "text-pop-encre")
                  }
                >
                  {valeur === null
                    ? "—"
                    : comptage
                      ? entier(valeur)
                      : montant(valeur)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </section>
  );
}
