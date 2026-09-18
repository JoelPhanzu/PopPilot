/**
 * PopPilot — controles et reserves de lecture.
 *
 * Ce bloc porte tout ce qui nuance les chiffres affiches au-dessus : bilan
 * desequilibre, comptes hors mapping, taux manquant, moyennes de periode
 * indisponibles, PAR calcule sur une extraction d'un autre mois.
 *
 * Il est place AVANT les tableaux, pas en note de bas de page. Les moteurs
 * prennent soin de renvoyer ces reserves plutot que de lisser en silence ; les
 * enterrer en fin d'ecran reviendrait a annuler cette precaution.
 */
import { entier, montant } from "@/lib/format";
import type { ControlesEtats, Indicateurs } from "@/lib/comptabilite";

type Reserve = { gravite: "alerte" | "info"; texte: string };

/** Quelques centimes d'ecart viennent des arrondis ; au-dela, c'est un defaut. */
const TOLERANCE_EQUILIBRE = 1;

function rassembler(
  controles: ControlesEtats | null,
  comptesNonMappes: string[],
  indicateurs: Indicateurs | null,
): Reserve[] {
  const reserves: Reserve[] = [];

  if (controles) {
    if (Math.abs(controles.bilan_equilibre_ecart) > TOLERANCE_EQUILIBRE) {
      reserves.push({
        gravite: "alerte",
        texte:
          `Le bilan ne boucle pas : ecart de ${montant(controles.bilan_equilibre_ecart)}. ` +
          "Tout ce qui en decoule est a verifier avant usage.",
      });
    }
    if (controles.comptes_non_mappes > 0) {
      const apercu = comptesNonMappes.slice(0, 12).join(", ");
      reserves.push({
        gravite: "alerte",
        texte:
          `${entier(controles.comptes_non_mappes)} compte(s) de la balance ne sont rattaches a ` +
          `aucune rubrique : ${apercu}${comptesNonMappes.length > 12 ? "…" : ""}. ` +
          "Leur montant manque donc au bilan.",
      });
    }
    if (controles.taux_absent) {
      reserves.push({
        gravite: "info",
        texte: `Montants CDF indisponibles : ${controles.taux_absent}`,
      });
    }
    if (!controles.ibp_deduit && controles.ibp_du_a_cet_arrete) {
      reserves.push({
        gravite: "alerte",
        texte:
          "Arrete annuel : l'IBP est du mais n'est pas deduit (grille de reintegrations DAF " +
          "non fournie). Le resultat net, le ROE et le ROA sont surevalues.",
      });
    }
  }

  if (indicateurs) {
    if (!indicateurs.moyennes_de_periode) {
      reserves.push({
        gravite: "info",
        texte:
          "Moyennes de periode indisponibles : les ratios de rentabilite portent sur le solde " +
          "de l'arrete, et non sur la moyenne avec le 31/12 precedent.",
      });
    }
    for (const texte of Object.values(indicateurs.avertissements)) {
      reserves.push({ gravite: "info", texte });
    }
  }

  return reserves;
}

export function BlocControles({
  controles,
  comptesNonMappes = [],
  indicateurs,
}: {
  controles: ControlesEtats | null;
  comptesNonMappes?: string[];
  indicateurs: Indicateurs | null;
}) {
  const reserves = rassembler(controles, comptesNonMappes, indicateurs);

  if (reserves.length === 0) {
    return (
      <section className="rounded-xl border border-pop-ok/25 bg-pop-ok/5 px-4 py-3">
        <p className="text-sm font-medium text-pop-ok">
          Controles passes : bilan equilibre, aucun compte hors mapping, aucune reserve de calcul.
        </p>
      </section>
    );
  }

  const alertes = reserves.filter((r) => r.gravite === "alerte");

  return (
    <section
      className={
        alertes.length > 0
          ? "rounded-xl border border-pop-danger/25 bg-pop-danger/5 px-4 py-3"
          : "rounded-xl border border-pop-alerte/25 bg-pop-alerte/5 px-4 py-3"
      }
    >
      <h2
        className={
          alertes.length > 0
            ? "text-sm font-semibold text-pop-danger"
            : "text-sm font-semibold text-pop-alerte"
        }
      >
        {alertes.length > 0
          ? "Reserves sur ces chiffres — a lever avant de les publier"
          : "Precisions de lecture"}
      </h2>
      <ul className="mt-2 space-y-1.5">
        {reserves.map((reserve) => (
          <li
            key={reserve.texte}
            className={
              reserve.gravite === "alerte"
                ? "text-[13px] leading-relaxed text-pop-danger"
                : "text-[13px] leading-relaxed text-pop-gris"
            }
          >
            {reserve.texte}
          </li>
        ))}
      </ul>
    </section>
  );
}
