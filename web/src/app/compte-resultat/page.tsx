/**
 * PopPilot — compte d'exploitation PAR AGENCE (chantier 3).
 *
 * Affiche le fichier mensuel du CDG tel qu'importe (GET /compte-resultat-agence) :
 * le RESULTAT de chaque agence en tete (vert = benefice, rouge = perte), puis le
 * detail des produits et des charges. Aucun montant n'est calcule ici — le total
 * est celui renvoye par l'API (somme des agences visibles).
 *
 * Cloisonnement : un role AGENCE ne recoit que sa colonne (API).
 */
import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { Coquille } from "@/composants/Coquille";
import { ExportSections } from "@/composants/ExportSections";
import { AvisArrete } from "@/composants/AvisArrete";
import { arreteAffiche } from "@/lib/arretes";
import { SelecteurArrete } from "@/composants/SelecteurArrete";
import { FournisseurSession } from "@/composants/ContexteSession";
import { sessionCourante } from "@/lib/session";
import { appelerApi } from "@/lib/api";
import { dateLongue, montant } from "@/lib/format";

export const metadata: Metadata = {
  title: "Compte d'exploitation — PopPilot",
  description: "Resultat et detail des produits et charges par agence.",
};

export const dynamic = "force-dynamic";

type Poste = {
  poste: string;
  nature: "produit" | "charge" | "total_produits" | "total_charges" | "resultat";
  montants: Record<string, number>;
  total: number;
};
type Reponse = { arrete: string; agences: string[]; portee: string; postes: Poste[] };

/** « AGENCE DE VICTOIRE » → « Victoire » : les en-tetes de colonnes restent lisibles. */
function court(agence: string): string {
  const nom = agence.replace(/^AGENCE\s+(DE\s+)?/i, "").trim();
  return nom.charAt(0) + nom.slice(1).toLowerCase();
}

function Signe({ valeur, fort = false }: { valeur: number; fort?: boolean }) {
  return (
    <span className={`${fort ? "font-semibold" : ""} ${valeur >= 0 ? "text-pop-ok" : "text-pop-danger"}`}>
      {valeur >= 0 ? "+" : "−"}
      {montant(Math.abs(valeur))}
    </span>
  );
}

export default async function PageCompteResultat({
  searchParams,
}: {
  searchParams: Promise<{ arrete?: string }>;
}) {
  const { profil, jeton, avertissement } = await sessionCourante();
  if (profil === null) {
    if (avertissement) redirect("/login");
    redirect("/login?suite=/compte-resultat");
  }

  const { arrete: demande } = await searchParams;
  // Regle du calendrier : dernier compte d'exploitation enregistre a la date choisie.
  const liste = profil.demo ? null : await arreteAffiche("compte_resultat_agence", demande, jeton);
  const arretes = liste?.disponibles ?? [];
  const arrete = liste?.erreur ? null : liste?.arrete ?? null;
  const cr =
    arrete && !profil.demo
      ? await appelerApi<Reponse>(`/compte-resultat-agence?arrete=${arrete}`, jeton)
      : null;

  const th = "px-3 py-2.5 text-right text-[12px] font-semibold uppercase tracking-wide text-white/90";
  const td = "chiffres px-3 py-2 text-right text-[13px] text-pop-encre";

  return (
    <FournisseurSession profil={profil}>
      <Coquille profil={profil} actif="/compte-resultat">
        <div className="space-y-6">
          <header className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <h1 className="text-2xl font-semibold tracking-tight text-pop-encre">
                Compte d&apos;exploitation par agence
              </h1>
              <p className="mt-1 text-sm text-pop-gris">
                {arrete ? `Situation de ${dateLongue(arrete)}` : "Aucun mois importe"} &middot; source :
                fichier mensuel du controle de gestion (MICROPOP = somme des agences, verifie a
                l&apos;import).
              </p>
            </div>
            {cr?.ok && arrete && (
              <ExportSections
                titre="Compte d'exploitation par agence"
                sousTitre={`Situation de ${dateLongue(arrete)}`}
                nom={`PopPilot_compte_exploitation_${arrete}`}
                imprimer
                sections={[{
                  colonnes: [
                    { libelle: "Poste", cle: "poste" },
                    ...cr.donnees.agences.map((a) => ({ libelle: court(a), cle: a })),
                    ...(cr.donnees.agences.length > 1 ? [{ libelle: "MICROPOP", cle: "__total" }] : []),
                  ],
                  lignes: cr.donnees.postes.map((p) => ({ poste: p.poste, ...p.montants, __total: p.total })),
                }]}
              />
            )}
          </header>

          {arretes.length > 0 && arrete && (
            <div className="space-y-2">
              <SelecteurArrete key={arrete} arrete={arrete} />
              <AvisArrete resolu={liste} />
            </div>
          )}

          {profil.demo ? (
            <p className="text-sm text-pop-gris">Indisponible en demonstration.</p>
          ) : liste?.erreur ? (
            <p role="alert" className="text-sm text-pop-danger">{liste?.erreur}</p>
          ) : !arrete ? (
            <p className="text-sm text-pop-gris">
              Aucun compte de resultat par agence importe. L&apos;importer depuis la page Import
              (domaine « Compte de resultat par agence »).
            </p>
          ) : cr && !cr.ok ? (
            <p role="alert" className="text-sm text-pop-danger">{cr.erreur}</p>
          ) : cr ? (
            <>
              {(() => {
                const res = cr.donnees.postes.find((p) => p.nature === "resultat");
                if (!res) return null;
                return (
                  <section
                    aria-label="Resultat par agence"
                    className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-7"
                  >
                    {cr.donnees.agences.map((a) => (
                      <div key={a} className="rounded-xl border border-pop-bord bg-pop-carte p-4 shadow-sm">
                        <p className="text-[12px] font-medium text-pop-gris">{court(a)}</p>
                        <p className="chiffres mt-1 text-lg">
                          <Signe valeur={res.montants[a] ?? 0} fort />
                        </p>
                        <p className="text-[11px] text-pop-gris">
                          {(res.montants[a] ?? 0) >= 0 ? "benefice" : "perte"}
                        </p>
                      </div>
                    ))}
                    {cr.donnees.agences.length > 1 && (
                      <div className="rounded-xl border-2 border-pop-bleu bg-pop-carte p-4 shadow-sm">
                        <p className="text-[12px] font-semibold text-pop-bleu">MICROPOP</p>
                        <p className="chiffres mt-1 text-lg">
                          <Signe valeur={res.total} fort />
                        </p>
                        <p className="text-[11px] text-pop-gris">resultat consolide</p>
                      </div>
                    )}
                  </section>
                );
              })()}

              <section className="overflow-x-auto rounded-xl border border-pop-bord bg-pop-carte shadow-sm">
                <table className="w-full min-w-[56rem] border-collapse text-sm">
                  <thead className="bg-pop-bleu">
                    <tr>
                      <th className={`${th} text-left`}>Poste</th>
                      {cr.donnees.agences.map((a) => (
                        <th key={a} className={th}>
                          {court(a)}
                        </th>
                      ))}
                      {cr.donnees.agences.length > 1 && <th className={th}>MICROPOP</th>}
                    </tr>
                  </thead>
                  <tbody>
                    {cr.donnees.postes.map((p) => {
                      const total = p.nature === "total_produits" || p.nature === "total_charges";
                      const resultat = p.nature === "resultat";
                      return (
                        <tr
                          key={p.poste}
                          className={`border-b border-pop-bord/60 ${
                            total ? "bg-pop-fond font-semibold" : resultat ? "border-t-2 border-t-pop-bleu" : ""
                          }`}
                        >
                          <td className={`px-3 py-2 text-[13px] ${total || resultat ? "font-semibold text-pop-encre" : "text-pop-gris"}`}>
                            {p.poste}
                          </td>
                          {cr.donnees.agences.map((a) => (
                            <td key={a} className={td}>
                              {resultat ? <Signe valeur={p.montants[a] ?? 0} fort /> : montant(p.montants[a] ?? 0)}
                            </td>
                          ))}
                          {cr.donnees.agences.length > 1 && (
                            <td className={`${td} font-semibold`}>
                              {resultat ? <Signe valeur={p.total} fort /> : montant(p.total)}
                            </td>
                          )}
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </section>
            </>
          ) : null}
        </div>
      </Coquille>
    </FournisseurSession>
  );
}
