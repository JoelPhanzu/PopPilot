/**
 * PopPilot — reserves de lecture du module comptabilite.
 *
 * Tout ce que les moteurs signalent eux-memes est remonte ICI, sur l'ecran ou
 * les chiffres sont lus, et non dans un journal que personne n'ouvre : comptes
 * non mappes, taux de change absent, moyennes de periode indisponibles, PAR
 * credit d'un autre mois que la balance, IBP non deduit au 31/12, et les
 * `avertissements` que le moteur d'indicateurs publie nommement.
 *
 * Aucune de ces reserves n'invalide les chiffres ; toutes changent la facon de
 * les lire. Un ROE calcule sur un solde ponctuel au lieu d'une moyenne de
 * periode n'est pas faux, il ne repond simplement pas a la meme question — et
 * c'est le genre de nuance qui se perd exactement au moment ou elle compte.
 */
import type { EtatsFinanciers, Indicateurs } from "@/lib/comptabilite";
import { LIBELLES_AGREGAT } from "@/lib/comptabilite";
import { dateLongue, entier } from "@/lib/format";

/** Une reserve : son intitule, son explication, et sa gravite d'affichage. */
type Reserve = { cle: string; titre: string; detail: string; bloquant?: boolean };

/** Libelle d'un indicateur ou d'un agregat cite par un avertissement moteur. */
function nommer(cle: string): string {
  return LIBELLES_AGREGAT[cle] ?? cle;
}

function rassembler(
  etats: EtatsFinanciers | null,
  indicateurs: Indicateurs | null,
): Reserve[] {
  const reserves: Reserve[] = [];

  if (etats) {
    const { controles, comptes_non_mappes } = etats;

    if (controles.comptes_non_mappes > 0) {
      // Un compte non mappe est absent du bilan : c'est le seul cas ou une
      // reserve remet en cause les totaux eux-memes.
      const apercu = comptes_non_mappes.slice(0, 12).join(", ");
      const reste = comptes_non_mappes.length - 12;
      reserves.push({
        cle: "non_mappes",
        bloquant: true,
        titre: `${entier(controles.comptes_non_mappes)} compte(s) de la balance non reconnus par le mapping`,
        detail:
          `Ces comptes n'entrent dans aucune rubrique : ils manquent au bilan et au resultat. ` +
          `A traiter dans engine/etats_financiers.py (MAPPING, §40)` +
          (apercu ? ` — ${apercu}${reste > 0 ? `, +${entier(reste)} autres` : ""}.` : "."),
      });
    }

    if (controles.taux_absent) {
      reserves.push({
        cle: "taux",
        titre: "Aucun taux USD/CDF saisi pour cet arrete",
        detail:
          `${controles.taux_absent} Les montants USD restent exacts ; aucun montant CDF ` +
          "n'est derive, et les moyennes de periode peuvent manquer. Le taux ne se fige jamais (§42) : " +
          "il se saisit (ingest/taux_change.saisir_taux).",
      });
    }

    if (controles.ibp_du_a_cet_arrete && !controles.ibp_deduit) {
      reserves.push({
        cle: "ibp",
        titre: "Arrete annuel : l'impot sur le benefice n'est pas deduit",
        detail:
          "Au 31/12, le « resultat net » affiche est en realite le resultat COMPTABLE, avant IBP " +
          "(§67) — la grille de reintegrations DAF n'est pas fournie. Le ROE et le ROA qui en " +
          "decoulent sont donc surevalues.",
      });
    }
  }

  if (indicateurs) {
    if (!indicateurs.moyennes_de_periode) {
      reserves.push({
        cle: "moyennes",
        titre: "Moyennes de periode indisponibles",
        detail:
          "Le 31/12 precedent" +
          (indicateurs.date_debut_exercice
            ? ` (${dateLongue(indicateurs.date_debut_exercice)})`
            : "") +
          " n'est pas charge : le ROE, le ROA, l'efficacite et le rendement portent sur le solde " +
          "ponctuel de l'arrete, et non sur une moyenne de periode.",
      });
    }

    const par = indicateurs.par_credit;
    if (par && par.meme_mois === false) {
      reserves.push({
        cle: "par_mois",
        titre: "PAR issu d'une extraction credit d'un autre mois",
        detail:
          `Le PAR vient de l'extraction du ${par.date_credit ? dateLongue(par.date_credit) : "?"}, ` +
          "alors que la balance porte un autre arrete. L'invariant PAR = compte 39 n'est pas " +
          "verifiable dans ces conditions.",
      });
    }
    if (par === null) {
      reserves.push({
        cle: "par_absent",
        titre: "Aucune extraction credit rattachee a cet arrete",
        detail:
          "Les indicateurs de qualite du portefeuille (A1) s'appuient sur le credit de la Phase 1, " +
          "source unique du PAR. Importer l'extraction credit du mois.",
      });
    }

    for (const [cle, message] of Object.entries(indicateurs.avertissements ?? {})) {
      reserves.push({
        cle: `moteur_${cle}`,
        titre: nommer(cle),
        detail: message,
      });
    }
  }

  return reserves;
}

export function ReservesComptables({
  etats,
  indicateurs,
}: {
  etats: EtatsFinanciers | null;
  indicateurs: Indicateurs | null;
}) {
  const reserves = rassembler(etats, indicateurs);
  if (reserves.length === 0) return null;

  return (
    <section className="overflow-hidden rounded-xl border border-pop-alerte/30 bg-pop-alerte/5">
      <header className="border-b border-pop-alerte/20 px-5 py-3">
        <h2 className="text-[13px] font-semibold uppercase tracking-wide text-pop-alerte">
          Reserves de lecture ({entier(reserves.length)})
        </h2>
        <p className="mt-0.5 text-[12px] text-pop-gris">
          Signalees par les moteurs eux-memes. Elles ne rendent pas les chiffres faux&nbsp;; elles
          changent la facon de les lire.
        </p>
      </header>

      <ul className="divide-y divide-pop-alerte/15">
        {reserves.map((r) => (
          <li key={r.cle} className="px-5 py-3">
            <p
              className={
                r.bloquant
                  ? "text-[13px] font-semibold text-pop-danger"
                  : "text-[13px] font-medium text-pop-encre"
              }
            >
              {r.titre}
            </p>
            <p className="mt-0.5 text-[12px] leading-relaxed text-pop-gris">{r.detail}</p>
          </li>
        ))}
      </ul>
    </section>
  );
}
