/**
 * PopPilot — le tableau du DailyTool, colonne par colonne, ligne MICROPOP en tete.
 *
 * Chiffres de l'API seulement. Taux recus en FRACTIONS, affiches en %. Une valeur
 * absente (objectif non importe, champ reserve au role) s'affiche « — », jamais 0.
 * Groupes de colonnes : Objectifs & realisation (flux) · Portefeuille (stock) ·
 * Risque · Migrations (M-1 → arrete) · Encaissements (periode) · Potentiel fin de
 * mois · Rappel M-1.
 *
 * Declinaison DANS le tableau : un clic sur une designation descend d'un niveau
 * (agence → ses superviseurs → leurs agents → leurs clients). Les liens sont
 * calcules par la page (`liens`, cle « agence|designation »).
 */
import Link from "next/link";
import { entier, montant, pourcent } from "@/lib/format";
import type { LigneTdb } from "@/lib/credit-tdb";

type Col = { titre: string; groupe: string; valeur: (l: LigneTdb) => string; gauche?: boolean };

const n = (v: number | null | undefined) => (v == null ? "—" : entier(v));
const m = (v: number | null | undefined) => (v == null ? "—" : montant(v));
const p = (v: number | null | undefined) => (v == null ? "—" : pourcent(v * 100));
const d = (v: number | null | undefined) => (v == null ? "—" : v.toLocaleString("fr-FR", { maximumFractionDigits: 2 }));

const COLONNES: Col[] = [
  { groupe: "Ligne", titre: "Fonction", valeur: (l) => l.fonction, gauche: true },
  { groupe: "Ligne", titre: "Agents", valeur: (l) => n(l.nb_agents) },
  { groupe: "Objectifs & realisation (periode)", titre: "#P15 objectif", valeur: (l) => n(l.p15_objectif) },
  { groupe: "Objectifs & realisation (periode)", titre: "#P15", valeur: (l) => n(l.p15) },
  { groupe: "Objectifs & realisation (periode)", titre: "% P15", valeur: (l) => (l.p15_objectif ? pourcent((l.p15 / l.p15_objectif) * 100) : "—") },
  { groupe: "Objectifs & realisation (periode)", titre: "#Objectif decaissement", valeur: (l) => n(l.objectif_nombre) },
  { groupe: "Objectifs & realisation (periode)", titre: "Nombre decaisse", valeur: (l) => n(l.decaisse_nombre) },
  { groupe: "Objectifs & realisation (periode)", titre: "% realisation", valeur: (l) => p(l.pct_realisation_nombre) },
  { groupe: "Objectifs & realisation (periode)", titre: "Productivite", valeur: (l) => d(l.productivite) },
  { groupe: "Objectifs & realisation (periode)", titre: "Objectif volume", valeur: (l) => m(l.objectif_volume) },
  { groupe: "Objectifs & realisation (periode)", titre: "Volume decaisse", valeur: (l) => m(l.decaisse_volume) },
  { groupe: "Objectifs & realisation (periode)", titre: "% volume", valeur: (l) => p(l.pct_realisation_volume) },
  { groupe: "Portefeuille (stock)", titre: "Nombre de clients", valeur: (l) => n(l.nb_clients) },
  { groupe: "Portefeuille (stock)", titre: "Credits", valeur: (l) => n(l.nb_credits) },
  { groupe: "Portefeuille (stock)", titre: "Encours de credit", valeur: (l) => m(l.encours) },
  { groupe: "Portefeuille (stock)", titre: "Croissance", valeur: (l) => p(l.croissance) },
  { groupe: "Risque (stock)", titre: "PAR1", valeur: (l) => m(l.par1) },
  { groupe: "Risque (stock)", titre: "PAR30", valeur: (l) => m(l.par30) },
  { groupe: "Risque (stock)", titre: "PAR90", valeur: (l) => m(l.par90) },
  { groupe: "Risque (stock)", titre: "% PAR1", valeur: (l) => p(l.pct_par1) },
  { groupe: "Risque (stock)", titre: "% PAR30", valeur: (l) => p(l.pct_par30) },
  { groupe: "Risque (stock)", titre: "% PAR90", valeur: (l) => p(l.pct_par90) },
  { groupe: "Risque (stock)", titre: "Provisions", valeur: (l) => m(l.provisions) },
  { groupe: "Risque (stock)", titre: "% provisions", valeur: (l) => (l.provisions == null || !l.encours ? "—" : pourcent((l.provisions / l.encours) * 100)) },
  { groupe: "Risque (stock)", titre: "Provisions M-1", valeur: (l) => m(l.provisions_m1) },
  { groupe: "Risque (stock)", titre: "Variation de provision", valeur: (l) => m(l.variation_provision) },
  { groupe: "Migrations (M-1 → arrete)", titre: "Cout du risque", valeur: (l) => m(l.cout_du_risque) },
  { groupe: "Migrations (M-1 → arrete)", titre: "#Entre dans la PAR", valeur: (l) => n(l.entree_par_nb) },
  { groupe: "Migrations (M-1 → arrete)", titre: "Entre dans la PAR", valeur: (l) => m(l.entree_par_montant) },
  ...["31-60", "61-90", "91-180", "181-360", "361+"].map((t) => ({
    groupe: "Migrations (M-1 → arrete)",
    titre: `Migration vers ${t}`,
    valeur: (l: LigneTdb) => m(l.migration_vers?.[t]),
  })),
  { groupe: "Encaissements (periode)", titre: "Interets encaisses", valeur: (l) => m(l.interets_encaisses) },
  { groupe: "Encaissements (periode)", titre: "Capital rembourse", valeur: (l) => m(l.capital_rembourse) },
  { groupe: "Encaissements (periode)", titre: "Penalites", valeur: (l) => m(l.penalites_encaissees) },
  { groupe: "Encaissements (periode)", titre: "Recouvre sur PAR", valeur: (l) => m(l.recouvre_sur_par) },
  { groupe: "Potentiel fin de mois (si rien ne change)", titre: "Potentiel cout du risque", valeur: (l) => m(l.potentiel_cout_du_risque) },
  { groupe: "Potentiel fin de mois (si rien ne change)", titre: "#Potentiel migration", valeur: (l) => n(l.potentiel_migration_nb) },
  { groupe: "Potentiel fin de mois (si rien ne change)", titre: "Potentiel migration", valeur: (l) => m(l.potentiel_migration_montant) },
  { groupe: "Rappel M-1", titre: "Encours M-1", valeur: (l) => m(l.encours_m1) },
  { groupe: "Rappel M-1", titre: "#Clients M-1", valeur: (l) => n(l.nb_clients_m1) },
  { groupe: "Rappel M-1", titre: "#Credits M-1", valeur: (l) => n(l.nb_credits_m1) },
];

const ETIQUETTE: Record<string, string> = { orphelin: "hors roster", gele: "agence non productive" };

export function TableauDailyTool({
  lignes,
  liens = {},
}: {
  lignes: LigneTdb[];
  /** « agence|designation » → lien vers le niveau inferieur (absent = pas de descente). */
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
          {lignes.map((l, i) => (
            <tr
              key={`${l.agence}-${l.designation}`}
              className={`border-b border-pop-bord/60 ${i === 0 ? "bg-pop-fond font-semibold" : ""}`}
            >
              <th className={`sticky left-0 z-10 whitespace-nowrap px-3 py-1.5 text-left font-medium text-pop-encre ${i === 0 ? "bg-pop-fond" : "bg-pop-carte"}`}>
                {liens[`${l.agence}|${l.designation}`] ? (
                  <Link href={liens[`${l.agence}|${l.designation}`]} className="lien-pop" title="Detailler cette ligne">
                    {l.designation} ›
                  </Link>
                ) : (
                  l.designation
                )}
                {l.fonction !== "AGENCE" && l.fonction !== "FILIALE" && (
                  <span className="ml-1 text-[11px] font-normal text-pop-gris">({l.agence})</span>
                )}
                {ETIQUETTE[l.statut] && (
                  <span className="ml-1 rounded-full bg-pop-alerte/10 px-1.5 text-[10px] text-pop-alerte">
                    {ETIQUETTE[l.statut]}
                  </span>
                )}
              </th>
              {COLONNES.map((c) => (
                <td key={c.titre} className={`chiffres whitespace-nowrap px-2.5 py-1.5 text-pop-encre ${c.gauche ? "text-left" : "text-right"}`}>
                  {c.valeur(l)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
