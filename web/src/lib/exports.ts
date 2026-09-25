/**
 * PopPilot — sections d'export (CSV / Excel / PDF) des ecrans comptabilite et budget.
 *
 * Aucune valeur n'est calculee : on reprend telles quelles les lignes renvoyees par
 * l'API (etats detailles, indicateurs, agregats, lignes budgetaires).
 */
import type { SectionExport } from "@/composants/ExportSections";
import type { EtatsDetailles, EtatsFinanciers, Indicateurs, LigneEtat } from "@/lib/comptabilite";
import { INDICATEURS_CONNUS, LIBELLES_AGREGAT } from "@/lib/comptabilite";
import type { LigneBudget } from "@/lib/budget";

const COLONNES_ETAT = [
  { libelle: "Code", cle: "code" },
  { libelle: "Libelle", cle: "libelle" },
  { libelle: "Nature", cle: "nature" },
  { libelle: "Montant", cle: "montant" },
];

const lignesEtat = (l: LigneEtat[]) =>
  l.map(({ code, libelle, nature, montant }) => ({ code, libelle, nature, montant }));

export function sectionsComptabilite(
  etats: EtatsFinanciers | null,
  detail: EtatsDetailles | null,
  indicateurs: Indicateurs | null,
): SectionExport[] {
  const sections: SectionExport[] = [];
  if (detail) {
    sections.push(
      { titre: "Bilan - actif", colonnes: COLONNES_ETAT, lignes: lignesEtat(detail.actif) },
      { titre: "Bilan - passif", colonnes: COLONNES_ETAT, lignes: lignesEtat(detail.passif) },
      { titre: "Compte de resultat", colonnes: COLONNES_ETAT, lignes: lignesEtat(detail.resultat) },
    );
  } else if (etats) {
    const rubriques = (r: Record<string, number>) =>
      Object.entries(r).map(([rubrique, montant]) => ({ rubrique, montant }));
    const col = [{ libelle: "Rubrique", cle: "rubrique" }, { libelle: "Montant", cle: "montant" }];
    sections.push(
      { titre: "Bilan - actif", colonnes: col, lignes: [...rubriques(etats.actif), { rubrique: "TOTAL ACTIF", montant: etats.total_actif }] },
      { titre: "Bilan - passif", colonnes: col, lignes: [...rubriques(etats.passif), { rubrique: "TOTAL PASSIF", montant: etats.total_passif }] },
      {
        titre: "Compte de resultat", colonnes: col, lignes: [
          { rubrique: "Produits", montant: etats.produits }, { rubrique: "Charges", montant: etats.charges },
          { rubrique: "Resultat comptable", montant: etats.resultat_comptable },
          { rubrique: "Resultat net", montant: etats.resultat_net },
        ],
      },
    );
  }
  if (indicateurs) {
    const libelle = (code: string) => INDICATEURS_CONNUS.find((i) => i.code === code)?.libelle ?? code;
    sections.push({
      titre: "Indicateurs prudentiels",
      colonnes: [
        { libelle: "Code", cle: "code" }, { libelle: "Indicateur", cle: "libelle" },
        { libelle: "Valeur", cle: "valeur" }, { libelle: "Norme", cle: "norme" },
        { libelle: "Numerateur", cle: "num" }, { libelle: "Denominateur", cle: "den" },
        { libelle: "Motif (si absent)", cle: "motif" },
      ],
      lignes: Object.entries(indicateurs.indicateurs).map(([code, i]) => ({ code, libelle: libelle(code), ...i })),
    });
    sections.push({
      titre: "Agregats",
      colonnes: [{ libelle: "Agregat", cle: "agregat" }, { libelle: "Valeur", cle: "valeur" }],
      lignes: Object.entries(indicateurs.agregats).map(([cle, valeur]) => ({
        agregat: LIBELLES_AGREGAT[cle] ?? cle, valeur,
      })),
    });
  }
  return sections;
}

export function sectionsBudget(lignes: LigneBudget[]): SectionExport[] {
  return [{
    titre: "Suivi budgetaire",
    colonnes: [
      { libelle: "Ligne", cle: "ligne" }, { libelle: "Sens", cle: "sens" },
      { libelle: "Budget du mois", cle: "budget_mois" }, { libelle: "Realise du mois", cle: "realise_mois" },
      { libelle: "Ecart du mois", cle: "ecart_mois" }, { libelle: "% realisation (rapport)", cle: "pct_realisation" },
      { libelle: "Realise cumule", cle: "realise_cumule" }, { libelle: "Budget annuel", cle: "budget_annuel" },
      { libelle: "Ecart annuel", cle: "ecart_annuel" }, { libelle: "% progression (rapport)", cle: "pct_progression" },
      { libelle: "Budget cumule a date", cle: "budget_cumule_a_date" }, { libelle: "Ecart a date", cle: "ecart_a_date" },
      { libelle: "% realisation a date (rapport)", cle: "pct_realisation_a_date" },
    ],
    lignes,
  }];
}
