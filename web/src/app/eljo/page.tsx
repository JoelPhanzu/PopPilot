/**
 * PopPilot — Eljo Smart : questions en langage naturel sur les donnees.
 *
 * Eljo ne calcule rien et n'invente rien : il comprend la question, l'API
 * appelle le moteur valide correspondant et renvoie la valeur exacte. Un role
 * AGENCE n'interroge que son agence. Chaque echange est trace (eljo_conversation).
 */
import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { Coquille } from "@/composants/Coquille";
import { FournisseurSession } from "@/composants/ContexteSession";
import { QuestionEljo } from "@/composants/QuestionEljo";
import { sessionCourante } from "@/lib/session";
import { appelerApi } from "@/lib/api";
import { montant } from "@/lib/format";

export const metadata: Metadata = {
  title: "Eljo Smart — PopPilot",
  description: "Poser une question sur les donnees de pilotage.",
};

export const dynamic = "force-dynamic";

type Historique = {
  echanges: { question: string; reponse: string; valeur: number | null; horodatage: string | null }[];
};

export default async function PageEljo() {
  const { profil, jeton, avertissement } = await sessionCourante();
  if (profil === null) {
    if (avertissement) redirect("/login");
    redirect("/login?suite=/eljo");
  }
  const h = profil.demo ? null : await appelerApi<Historique>("/eljo/historique?limite=30", jeton);

  return (
    <FournisseurSession profil={profil}>
      <Coquille profil={profil} actif="/eljo">
        <div className="mx-auto max-w-3xl space-y-6">
          <header>
            <h1 className="text-2xl font-semibold tracking-tight text-pop-encre">Eljo Smart</h1>
            <p className="mt-1 text-sm text-pop-gris">
              Posez une question sur le PAR, l&apos;encours, les provisions, les decaissements,
              l&apos;epargne ou le resultat. Eljo repond avec le chiffre des moteurs valides,
              date et perimetre a l&apos;appui — jamais une estimation.
            </p>
          </header>

          <QuestionEljo />

          <section aria-label="Historique" className="space-y-3">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-pop-gris">
              Vos derniers echanges
            </h2>
            {h === null ? (
              <p className="text-sm text-pop-gris">Pas d&apos;historique en demonstration.</p>
            ) : !h.ok ? (
              <p className="text-sm text-pop-danger">{h.erreur}</p>
            ) : h.donnees.echanges.length === 0 ? (
              <p className="text-sm text-pop-gris">Aucune question posee pour l&apos;instant.</p>
            ) : (
              [...h.donnees.echanges].reverse().map((e, i) => (
                <article key={`${e.horodatage}-${i}`} className="space-y-1.5">
                  <p className="ml-auto w-fit max-w-[85%] rounded-2xl rounded-br-sm bg-pop-bleu px-3 py-2 text-sm text-white">
                    {e.question}
                  </p>
                  <div className="w-fit max-w-[85%] rounded-2xl rounded-bl-sm border border-pop-bord bg-pop-carte px-3 py-2 text-sm text-pop-encre">
                    {e.reponse}
                    {e.valeur !== null && (
                      <span className="chiffres ml-2 font-semibold text-pop-bleu">{montant(e.valeur)}</span>
                    )}
                  </div>
                </article>
              ))
            )}
          </section>
        </div>
      </Coquille>
    </FournisseurSession>
  );
}
