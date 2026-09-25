/**
 * PopPilot — tableau de bord EPARGNE, ligne MICROPOP (ou agence) en tete.
 *
 * Chiffres de l'API seulement ; taux en FRACTIONS affiches en %. Les colonnes
 * « USD d'origine » et « CDF d'origine » sont en devise d'emission : elles ne
 * s'additionnent pas entre elles (l'encours USD, lui, est homogene).
 * Un clic sur une designation descend d'un niveau (lien calcule par la page).
 */
import Link from "next/link";
import { entier, montant, pourcent } from "@/lib/format";
import type { LigneEpargneTdb } from "@/lib/epargne-tdb";

type Col = { titre: string; groupe: string; valeur: (l: LigneEpargneTdb) => string };
const m = (v: number | null | undefined) => (v == null ? "—" : montant(v));
const n = (v: number | null | undefined) => (v == null ? "—" : entier(v));
const p = (v: number | null | undefined) => (v == null ? "—" : pourcent(v * 100));

const COLONNES: Col[] = [
  { groupe: "Stock (inventaire)", titre: "Comptes", valeur: (l) => n(l.nb_comptes) },
  { groupe: "Stock (inventaire)", titre: "Comptes crediteurs", valeur: (l) => n(l.nb_comptes_crediteurs) },
  { groupe: "Stock (inventaire)", titre: "Epargnants", valeur: (l) => n(l.nb_epargnants) },
  { groupe: "Stock (inventaire)", titre: "Encours (USD)", valeur: (l) => m(l.encours) },
  { groupe: "Stock (inventaire)", titre: "dont USD d'origine", valeur: (l) => m(l.encours_usd_origine) },
  { groupe: "Stock (inventaire)", titre: "dont CDF d'origine", valeur: (l) => m(l.encours_cdf_origine) },
  { groupe: "Par type (USD)", titre: "A vue", valeur: (l) => m(l.a_vue) },
  { groupe: "Par type (USD)", titre: "A terme", valeur: (l) => m(l.a_terme) },
  { groupe: "Par type (USD)", titre: "Obligatoire", valeur: (l) => m(l.obligatoire) },
  { groupe: "Evolution", titre: "Encours M-1", valeur: (l) => m(l.encours_m1) },
  { groupe: "Evolution", titre: "Croissance", valeur: (l) => p(l.croissance) },
  { groupe: "Flux de la periode (USD)", titre: "Depots", valeur: (l) => m(l.depots) },
  { groupe: "Flux de la periode (USD)", titre: "Retraits", valeur: (l) => m(l.retraits) },
  { groupe: "Flux de la periode (USD)", titre: "Collecte nette", valeur: (l) => m(l.collecte_nette) },
  { groupe: "Flux de la periode (USD)", titre: "#Comptes avec depot", valeur: (l) => n(l.nb_depots) },
  { groupe: "Flux de la periode (USD)", titre: "#Comptes avec retrait", valeur: (l) => n(l.nb_retraits) },
  { groupe: "Credit", titre: "Encours credit", valeur: (l) => m(l.encours_credit) },
  { groupe: "Credit", titre: "Couverture (epargne / credit)", valeur: (l) => p(l.couverture_credit) },
];

export function TableauEpargneTdb({
  lignes,
  liens = {},
}: {
  lignes: LigneEpargneTdb[];
  liens?: Record<string, string>;
}) {
  const groupes: { nom: string; taille: number }[] = [];
  for (const c of COLONNES) {
    const dernier = groupes[groupes.length - 1];
    if (dernier?.nom === c.groupe) dernier.taille += 1;
    else groupes.push({ nom: c.groupe, taille: 1 });
  }
  return (
    <section className="overflow-x-auto rounded-xl border border-pop-bord bg-pop-carte shadow-sm">
      <table className="min-w-max border-collapse text-[12px]">
        <thead>
          <tr className="bg-pop-bleu-2 text-white/90">
            <th className="sticky left-0 z-10 bg-pop-bleu-2" />
            {groupes.map((g) => (
              <th key={g.nom} colSpan={g.taille} className="border-l border-white/20 px-2 py-1 text-[11px] font-medium">
                {g.nom}
              </th>
            ))}
          </tr>
          <tr className="bg-pop-bleu text-white">
            <th className="sticky left-0 z-10 bg-pop-bleu px-3 py-2 text-left font-semibold">Designation</th>
            {COLONNES.map((c) => (
              <th key={c.titre} className="whitespace-nowrap px-2.5 py-2 text-right font-semibold">
                {c.titre}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {lignes.map((l, i) => {
            const lien = l.cle ? liens[l.cle] : undefined;
            return (
              <tr key={`${i}-${l.designation}`} className={`border-b border-pop-bord/60 ${i === 0 ? "bg-pop-fond font-semibold" : ""}`}>
                <th className={`sticky left-0 z-10 whitespace-nowrap px-3 py-1.5 text-left font-medium text-pop-encre ${i === 0 ? "bg-pop-fond" : "bg-pop-carte"}`}>
                  {lien ? (
                    <Link href={lien} className="lien-pop" title="Detailler cette ligne">
                      {l.designation} ›
                    </Link>
                  ) : (
                    l.designation
                  )}
                </th>
                {COLONNES.map((c) => (
                  <td key={c.titre} className="chiffres whitespace-nowrap px-2.5 py-1.5 text-right text-pop-encre">
                    {c.valeur(l)}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </section>
  );
}
