/**
 * PopPilot — tableau de bord EPARGNE, ligne MICROPOP (ou agence) en tete.
 *
 * Chiffres de l'API seulement ; taux en FRACTIONS affiches en %. Les colonnes
 * « USD d'origine » et « CDF d'origine » sont en devise d'emission : elles ne
 * s'additionnent pas entre elles (l'encours USD, lui, est homogene).
 * Un clic sur une designation descend d'un niveau (lien calcule par la page).
 *
 * Colonnes selon le niveau : une colonne SANS OBJET n'est pas affichee plutot que
 * remplie de tirets — nom et statut au niveau client ; type et devise au niveau
 * produit ; credit et couverture seulement par agence ou par client ; evolution
 * seulement si un inventaire du mois precedent est charge (le bandeau le dit).
 */
import Link from "next/link";
import { entier, montant, pourcent } from "@/lib/format";
import type { LigneEpargneTdb } from "@/lib/epargne-tdb";

type Niveau = "agence" | "produit" | "type" | "client";
type Col = { titre: string; groupe: string; valeur: (l: LigneEpargneTdb) => string; texte?: boolean; niveaux?: Niveau[] };
const m = (v: number | null | undefined) => (v == null ? "—" : montant(v));
const n = (v: number | null | undefined) => (v == null ? "—" : entier(v));
const p = (v: number | null | undefined) => (v == null ? "—" : pourcent(v * 100));
const t = (v: string | null | undefined) => v ?? "—";

const COLONNES: Col[] = [
  { groupe: "Client", titre: "Nom du client", valeur: (l) => t(l.nom_client), texte: true, niveaux: ["client"] },
  { groupe: "Client", titre: "Statut juridique", valeur: (l) => t(l.statut_juridique), texte: true, niveaux: ["client"] },
  { groupe: "Produit", titre: "Type de depot", valeur: (l) => t(l.type_depot), texte: true, niveaux: ["produit"] },
  { groupe: "Produit", titre: "Devise", valeur: (l) => t(l.devise), texte: true, niveaux: ["produit"] },
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
  { groupe: "Credit", titre: "Encours credit", valeur: (l) => m(l.encours_credit), niveaux: ["agence", "client"] },
  { groupe: "Credit", titre: "Couverture (epargne / credit)", valeur: (l) => p(l.couverture_credit), niveaux: ["agence", "client"] },
];

const LIBELLE_DESIGNATION: Record<Niveau, string> = {
  agence: "Agence", produit: "Produit (inventaire)", type: "Type de depot", client: "Code client",
};

export function TableauEpargneTdb({
  lignes,
  liens = {},
  niveau = "agence",
  avecEvolution = true,
  titre,
  description,
  exporter,
}: {
  lignes: LigneEpargneTdb[];
  liens?: Record<string, string>;
  niveau?: Niveau;
  /** Faux sans inventaire M-1 charge : Encours M-1 et Croissance seraient vides partout. */
  avecEvolution?: boolean;
  titre?: string;
  /** Ce que montre le tableau et sur quelle base (affiche sous le titre). */
  description?: React.ReactNode;
  exporter?: React.ReactNode;
}) {
  const colonnes = COLONNES.filter(
    (c) => (!c.niveaux || c.niveaux.includes(niveau)) && (avecEvolution || c.groupe !== "Evolution"),
  );
  const groupes: { nom: string; taille: number }[] = [];
  for (const c of colonnes) {
    const dernier = groupes[groupes.length - 1];
    if (dernier?.nom === c.groupe) dernier.taille += 1;
    else groupes.push({ nom: c.groupe, taille: 1 });
  }
  return (
    <section className="rounded-xl border border-pop-bord bg-pop-carte shadow-sm">
      {(titre || exporter) && (
        <div className="space-y-1 border-b border-pop-bord px-4 py-3">
          <div className="flex flex-wrap items-center gap-3">
            {titre && <h2 className="text-base font-semibold text-pop-encre">{titre}</h2>}
            <span className="text-xs text-pop-gris">{lignes.length - 1} ligne{lignes.length > 2 ? "s" : ""} + total</span>
            <div className="ml-auto">{exporter}</div>
          </div>
          {description && <div className="text-xs leading-relaxed text-pop-gris">{description}</div>}
        </div>
      )}
      <div className="overflow-x-auto">
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
              <th className="sticky left-0 z-10 bg-pop-bleu px-3 py-2 text-left font-semibold">{LIBELLE_DESIGNATION[niveau]}</th>
              {colonnes.map((c) => (
                <th key={c.titre} className={`whitespace-nowrap px-2.5 py-2 font-semibold ${c.texte ? "text-left" : "text-right"}`}>
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
                  {colonnes.map((c) => (
                    <td key={c.titre} className={`whitespace-nowrap px-2.5 py-1.5 text-pop-encre ${c.texte ? "text-left" : "chiffres text-right"}`}>
                      {i === 0 && c.texte ? "" : c.valeur(l)}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}
