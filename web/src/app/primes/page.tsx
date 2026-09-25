/**
 * PopPilot — primes hors « AC et SUP » (chantier 4).
 *
 *   1. Direction : % du resultat comptable (compte de resultat par agence importe)
 *   2. Fonctions support : realisations de l'agence × effectif saisi
 *   3. Recouvrement : tableau mensuel des montants recouvres
 *
 * Les montants viennent de l'API (engine/moteur_primes.py) : rien n'est calcule
 * ici. Reserve aux roles a acces total ; un role AGENCE est renvoye au credit.
 */
import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { Coquille } from "@/composants/Coquille";
import { FournisseurSession } from "@/composants/ContexteSession";
import { SelecteurArrete } from "@/composants/SelecteurArrete";
import { PrimesSupport } from "@/composants/PrimesSupport";
import { PrimesRecouvrement } from "@/composants/PrimesRecouvrement";
import { PrimesEpargneSuperviseurs } from "@/composants/PrimesEpargneSuperviseurs";
import { TableauPrimesAcSup } from "@/composants/TableauPrimesAcSup";
import { sessionCourante } from "@/lib/session";
import { aAccesTotal } from "@/lib/roles";
import { appelerApi } from "@/lib/api";
import { dateArreteValide, dateLongue, montant } from "@/lib/format";
import type { PrimesAcSup, PrimesDirection } from "@/lib/primes";

export const metadata: Metadata = {
  title: "Primes — PopPilot",
  description: "Primes : agents de credit et superviseurs, direction, support, epargne, recouvrement.",
};

export const dynamic = "force-dynamic";

/** Dernier jour du mois precedent : la periode de prime qu'on calcule d'habitude. */
function finDuMoisPrecedent(): string {
  const d = new Date();
  const fin = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), 0));
  return fin.toISOString().slice(0, 10);
}

function Section({ titre, regle, children }: { titre: string; regle: string; children: React.ReactNode }) {
  return (
    <section className="rounded-2xl border border-pop-bord bg-pop-carte p-5 shadow-sm lg:p-6">
      <h2 className="text-lg font-semibold text-pop-encre">{titre}</h2>
      <p className="mt-1 text-sm text-pop-gris">{regle}</p>
      <div className="mt-4">{children}</div>
    </section>
  );
}

export default async function PagePrimes({
  searchParams,
}: {
  searchParams: Promise<{ arrete?: string }>;
}) {
  const { profil, jeton, avertissement } = await sessionCourante();
  if (profil === null) {
    if (avertissement) redirect("/login");
    redirect("/login?suite=/primes");
  }
  if (!aAccesTotal(profil)) redirect("/credit");

  const { arrete: demande } = await searchParams;
  const arrete = demande && dateArreteValide(demande) ? demande : finDuMoisPrecedent();
  const [direction, acSup] = profil.demo
    ? [null, null]
    : await Promise.all([
        appelerApi<PrimesDirection>(`/primes/direction?arrete=${arrete}`, jeton),
        appelerApi<PrimesAcSup>(`/primes/ac-sup?arrete=${arrete}`, jeton),
      ]);

  const th = "px-3 py-2 text-right text-[12px] font-semibold uppercase tracking-wide text-pop-gris";
  const td = "chiffres px-3 py-2 text-right text-[13px]";

  return (
    <FournisseurSession profil={profil}>
      <Coquille profil={profil} actif="/primes">
        <div className="space-y-6">
          <header>
            <h1 className="text-2xl font-semibold tracking-tight text-pop-encre">Primes</h1>
            <p className="mt-1 text-sm text-pop-gris">
              Periode du {dateLongue(arrete)}. Calcul seulement&nbsp;: rien n&apos;est enregistre
              tant que la campagne n&apos;est pas validee.
            </p>
          </header>

          <SelecteurArrete key={arrete} arrete={arrete} />

          <Section
            titre="Agents de credit et superviseurs"
            regle="Cascade CALCUL_PRIMES « AC et SUP » : eligibilite (IL : encours ≥ 100 000 et ≥ 25 credits ; GL : ≥ 50 000 et ≥ 100), type (volume ≥ 100 % → 150 ; nombre ≥ 80 % → 90 ; les deux → 240) × coefficient PAR30 (≤ 3 % ×1 ; 3-5 % ×0,7 ; 5-7 % ×0,5 ; > 7 % ×0), + 60 si l'epargne des clients du portefeuille couvre ≥ 29,5 % de l'encours. Roster, objectifs et inventaire epargne du mois requis."
          >
            {acSup === null ? (
              <p className="text-sm text-pop-gris">Indisponible en demonstration.</p>
            ) : !acSup.ok ? (
              <p role="status" className="text-sm text-pop-alerte">{acSup.erreur}</p>
            ) : (
              <div className="space-y-5">
                {acSup.donnees.alertes.length > 0 && (
                  <ul className="list-disc pl-5 text-xs text-pop-alerte">
                    {acSup.donnees.alertes.map((a) => (
                      <li key={a}>{a}</li>
                    ))}
                  </ul>
                )}
                <TableauPrimesAcSup titre="Agents de credit" lignes={acSup.donnees.agents} total={acSup.donnees.total_agents} />
                <TableauPrimesAcSup titre="Superviseurs" lignes={acSup.donnees.superviseurs} total={acSup.donnees.total_superviseurs} />
                <p className="text-xs text-pop-gris">
                  Portefeuilles orphelins (agents hors roster) exclus des primes. La prime ne depend pas des interets
                  encaisses (indicateur de profitabilite, page Productivite).
                </p>
              </div>
            )}
          </Section>

          <Section
            titre="Direction"
            regle="Chef d'agence 1 %, adjoint 0,5 % du resultat comptable de l'agence. DG 1 %, DGA 0,6 %, DAF 0,3 %, responsable regional 1 % du resultat total. Pas de prime sur une perte."
          >
            {direction === null ? (
              <p className="text-sm text-pop-gris">Indisponible en demonstration.</p>
            ) : !direction.ok ? (
              <p className="text-sm text-pop-danger">{direction.erreur}</p>
            ) : (
              <div className="grid gap-6 lg:grid-cols-3">
                <div className="overflow-x-auto lg:col-span-2">
                  <table className="w-full border-collapse text-sm">
                    <thead>
                      <tr className="border-b border-pop-bord">
                        <th className={`${th} text-left`}>Agence</th>
                        <th className={th}>Resultat</th>
                        <th className={th}>Chef d&apos;agence</th>
                        <th className={th}>Adjoint</th>
                      </tr>
                    </thead>
                    <tbody>
                      {direction.donnees.agences.map((l) => (
                        <tr key={l.agence} className="border-b border-pop-bord/60">
                          <td className="px-3 py-2 font-medium text-pop-encre">{l.agence}</td>
                          <td className={`${td} font-semibold ${l.resultat >= 0 ? "text-pop-ok" : "text-pop-danger"}`}>
                            {montant(l.resultat)}
                          </td>
                          <td className={`${td} text-pop-encre`}>{montant(l.prime_chef_agence)}</td>
                          <td className={`${td} text-pop-encre`}>{montant(l.prime_adjoint)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div>
                  <p className="text-sm text-pop-gris">
                    Resultat total&nbsp;:{" "}
                    <span className="chiffres font-semibold text-pop-encre">
                      {montant(direction.donnees.direction_generale.resultat_total)}
                    </span>
                  </p>
                  <dl className="mt-3 space-y-1.5 text-sm">
                    {Object.entries(direction.donnees.direction_generale.primes).map(([fonction, prime]) => (
                      <div key={fonction} className="flex justify-between gap-4 border-b border-pop-bord/60 pb-1">
                        <dt className="text-pop-gris">{fonction}</dt>
                        <dd className="chiffres font-semibold text-pop-encre">{montant(prime)}</dd>
                      </div>
                    ))}
                  </dl>
                </div>
              </div>
            )}
          </Section>

          <Section
            titre="Fonctions support"
            regle="Meme montant pour chaque agent support d'une agence, selon les realisations DE L'AGENCE : +5 $ si l'objectif de decaissement est atteint, +10 $ si l'epargne atteint 60 % de l'encours, PAR30 ≤ 3 % → +30 $, 3-5 % → +20 $, 5-7 % → +10 $, > 7 % → 0."
          >
            {profil.demo ? (
              <p className="text-sm text-pop-gris">Indisponible en demonstration.</p>
            ) : (
              <PrimesSupport key={arrete} arrete={arrete} />
            )}
          </Section>

          <Section
            titre="Superviseurs epargne"
            regle="Fichier mensuel Agence | Cible | Realisation | %, range a son MOIS. La ligne TOTAL sert de controle. Palier sur la realisation TOTALE : ≥ 50 000 → 60 ; ≥ 70 000 → 100 ; ≥ 100 000 → 200 USD."
          >
            {profil.demo ? (
              <p className="text-sm text-pop-gris">Indisponible en demonstration.</p>
            ) : (
              <PrimesEpargneSuperviseurs />
            )}
          </Section>

          <Section
            titre="Recouvrement"
            regle="Agents : 1 % (91-180 j), 3 % (181-360 j), 5 % (radie) de leur montant recouvre. Responsable : 0,3 % / 0,5 % / 1 % du total recouvre. Fichier : Equipe | Agent | Agence | Montant 91-180 | Montant 181+ | Montant Radie."
          >
            {profil.demo ? (
              <p className="text-sm text-pop-gris">Indisponible en demonstration.</p>
            ) : (
              <PrimesRecouvrement />
            )}
          </Section>
        </div>
      </Coquille>
    </FournisseurSession>
  );
}
