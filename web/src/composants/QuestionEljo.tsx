"use client";

/**
 * PopPilot — zone de question d'Eljo Smart.
 *
 * Affiche la derniere reponse avec sa SOURCE (arrete, perimetre) : un chiffre
 * de pilotage sans sa date et son perimetre ne se discute pas. Le fil complet
 * est rendu par la page (historique trace cote API).
 */
import { useActionState } from "react";
import { poserQuestion, type EtatEljo } from "@/app/eljo/actions";
import { montant } from "@/lib/format";

const INITIAL: EtatEljo = { etat: "vierge" };
const EXEMPLES = [
  "Quel est le PAR de mai 2026 a Ozone ?",
  "Encours de aout 2026",
  "Decaissements de aout 2026 a Victoire",
  "Resultat de juillet 2026 a Lubumbashi",
];

export function QuestionEljo() {
  const [etat, agir, enCours] = useActionState(poserQuestion, INITIAL);
  const detail = etat.etat === "succes" ? etat.resultat.detail : undefined;

  return (
    <section className="rounded-2xl border border-pop-bord bg-pop-carte p-5 shadow-sm">
      <form action={agir} className="flex flex-col gap-3 sm:flex-row">
        <label htmlFor="question" className="sr-only">
          Question
        </label>
        <input
          id="question"
          name="question"
          required
          maxLength={500}
          placeholder="Ex. : PAR de mai 2026 a Ozone"
          className="flex-1 rounded-lg border border-pop-bord bg-white px-3 py-2 text-sm outline-none focus:border-pop-cyan focus:ring-2 focus:ring-pop-cyan/30"
        />
        <button
          type="submit"
          disabled={enCours}
          className="rounded-lg bg-pop-bleu px-4 py-2 text-sm font-medium text-white hover:bg-pop-bleu-2 disabled:opacity-45"
        >
          {enCours ? "Eljo cherche…" : "Demander"}
        </button>
      </form>
      <p className="mt-2 text-xs text-pop-gris">Exemples : {EXEMPLES.join(" · ")}</p>

      {etat.etat === "echec" && (
        <p role="alert" className="mt-4 text-sm text-pop-danger">
          {etat.message}
        </p>
      )}
      {etat.etat === "succes" && (
        <div role="status" className="mt-4 rounded-lg border border-pop-bord bg-pop-fond px-4 py-3">
          <p className="text-xs text-pop-gris">{etat.question}</p>
          <p className="mt-1 text-sm text-pop-encre">{etat.resultat.reponse}</p>
          {etat.resultat.valeur !== null && (
            <p className="chiffres mt-1 text-xl font-semibold text-pop-bleu">
              {montant(etat.resultat.valeur)}
            </p>
          )}
          {detail && (
            <p className="mt-1 text-xs text-pop-gris">
              Arrete {String(detail.arrete ?? "—")} · perimetre {String(detail.perimetre ?? "—")} · source :{" "}
              {etat.resultat.source ?? "moteurs PopPilot"}
            </p>
          )}
        </div>
      )}
    </section>
  );
}
