/**
 * PopPilot — module ARCHIVES : bibliotheque de rapports (versionnee) et series
 * temporelles d'indicateurs.
 *
 * Lecture : Direction, CDG, Audit. Depot, remplacement, edition, import et
 * calcul des series : Direction et CDG (l'API le verifie ; l'ecran ne propose
 * pas ce qui serait refuse).
 */
import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { Coquille } from "@/composants/Coquille";
import { FournisseurSession } from "@/composants/ContexteSession";
import { FormulaireArchive } from "@/composants/FormulaireArchive";
import { FormulairesSeries } from "@/composants/FormulairesSeries";
import { CourbeSerie } from "@/composants/CourbeSerie";
import { sessionCourante } from "@/lib/session";
import { aAccesTotal, peutEcrire } from "@/lib/roles";
import { appelerApi } from "@/lib/api";
import { montant } from "@/lib/format";
import {
  LIBELLES_INDICATEUR,
  type CatalogueSeries,
  type ListeArchives,
  type Serie,
} from "@/lib/archives";

export const metadata: Metadata = {
  title: "Archives — PopPilot",
  description: "Bibliotheque de rapports, edition en ligne et series d'indicateurs.",
};

export const dynamic = "force-dynamic";

function onglet(actif: boolean) {
  return `rounded-lg px-3 py-1.5 text-sm ${
    actif ? "bg-pop-bleu font-medium text-white" : "border border-pop-bord bg-pop-carte text-pop-gris hover:border-pop-cyan"
  }`;
}

export default async function PageArchives({
  searchParams,
}: {
  searchParams: Promise<{ onglet?: string; indicateur?: string; agence?: string }>;
}) {
  const { profil, jeton, avertissement } = await sessionCourante();
  if (profil === null) {
    if (avertissement) redirect("/login");
    redirect("/login?suite=/archives");
  }
  if (!aAccesTotal(profil)) redirect("/credit");
  const sp = await searchParams;
  const series = sp.onglet === "series";
  const ecriture = peutEcrire(profil) && !profil.demo;

  const liste = !series && !profil.demo ? await appelerApi<ListeArchives>("/archives", jeton) : null;
  const catalogue = series && !profil.demo ? await appelerApi<CatalogueSeries>("/series/indicateurs", jeton) : null;
  const indicateur =
    sp.indicateur ?? (catalogue?.ok ? catalogue.donnees.indicateurs[0]?.indicateur : undefined);
  const serie =
    series && indicateur && !profil.demo
      ? await appelerApi<Serie>(
          `/series?indicateur=${encodeURIComponent(indicateur)}${sp.agence ? `&agence=${encodeURIComponent(sp.agence)}` : ""}`,
          jeton,
        )
      : null;

  return (
    <FournisseurSession profil={profil}>
      <Coquille profil={profil} actif="/archives">
        <div className="space-y-6">
          <header>
            <h1 className="text-2xl font-semibold tracking-tight text-pop-encre">Archives</h1>
            <p className="mt-1 max-w-3xl text-sm text-pop-gris">
              Rapports deposes (remplacables : chaque nouvelle version garde la precedente),
              editables en ligne pour les tableurs, et courbes d&apos;evolution des indicateurs.
            </p>
          </header>

          <nav aria-label="Onglets" className="flex gap-2">
            <Link href="/archives" className={onglet(!series)}>
              Bibliotheque
            </Link>
            <Link href="/archives?onglet=series" className={onglet(series)}>
              Series temporelles
            </Link>
          </nav>

          {profil.demo && <p className="text-sm text-pop-gris">Indisponible en demonstration.</p>}

          {!series && liste && (
            <>
              {ecriture && (
                <section className="rounded-2xl border border-pop-bord bg-pop-carte p-5 shadow-sm">
                  <h2 className="mb-3 text-lg font-semibold text-pop-encre">Deposer un rapport</h2>
                  <FormulaireArchive />
                </section>
              )}
              {!liste.ok ? (
                <p role="alert" className="text-sm text-pop-danger">{liste.erreur}</p>
              ) : liste.donnees.archives.length === 0 ? (
                <p className="text-sm text-pop-gris">Aucun rapport archive pour l&apos;instant.</p>
              ) : (
                <section className="space-y-3">
                  <datalist id="types-rapport">
                    {liste.donnees.types.map((t) => (
                      <option key={t} value={t} />
                    ))}
                  </datalist>
                  {liste.donnees.archives.map((a) => (
                    <article key={a.id} className="rounded-xl border border-pop-bord bg-pop-carte p-4 shadow-sm">
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div>
                          <h3 className="font-semibold text-pop-encre">{a.titre}</h3>
                          <p className="text-xs text-pop-gris">
                            {a.type_rapport ?? "autre"} · {a.periode ?? "sans periode"} · .{a.format} ·
                            version {a.version}
                            {a.version > 1 ? " (les precedentes sont conservees)" : ""} · depose par{" "}
                            {a.depose_par ?? "—"} le {a.date_depot?.slice(0, 10) ?? "—"}
                          </p>
                        </div>
                        <div className="flex flex-wrap gap-3 text-sm">
                          <a href={`/api/archives/${a.id}`} className="lien-pop font-medium">
                            Telecharger
                          </a>
                          {a.editable && (
                            <Link href={`/archives/${a.id}`} className="lien-pop font-medium">
                              {ecriture ? "Editer en ligne" : "Consulter"}
                            </Link>
                          )}
                        </div>
                      </div>
                      {ecriture && (
                        <details className="mt-3">
                          <summary className="cursor-pointer text-sm text-pop-bleu-2">
                            Remplacer par une version plus a jour
                          </summary>
                          <div className="mt-3">
                            <FormulaireArchive remplace={a} />
                          </div>
                        </details>
                      )}
                    </article>
                  ))}
                </section>
              )}
            </>
          )}

          {series && catalogue && (
            <>
              {!catalogue.ok ? (
                <p role="alert" className="text-sm text-pop-danger">{catalogue.erreur}</p>
              ) : (
                <>
                  {catalogue.donnees.indicateurs.length > 0 && (
                    <section className="space-y-4 rounded-2xl border border-pop-bord bg-pop-carte p-5 shadow-sm">
                      <div className="flex flex-wrap gap-2">
                        {catalogue.donnees.indicateurs.map((i) => (
                          <Link
                            key={i.indicateur}
                            href={`/archives?onglet=series&indicateur=${i.indicateur}${sp.agence ? `&agence=${encodeURIComponent(sp.agence)}` : ""}`}
                            className={onglet(i.indicateur === indicateur)}
                          >
                            {LIBELLES_INDICATEUR[i.indicateur] ?? i.indicateur}
                          </Link>
                        ))}
                      </div>
                      <div className="flex flex-wrap gap-2 text-xs">
                        <Link
                          href={`/archives?onglet=series&indicateur=${indicateur}`}
                          className={onglet(!sp.agence)}
                        >
                          MICROPOP
                        </Link>
                        {catalogue.donnees.agences.map((a) => (
                          <Link
                            key={a}
                            href={`/archives?onglet=series&indicateur=${indicateur}&agence=${encodeURIComponent(a)}`}
                            className={onglet(sp.agence === a)}
                          >
                            {a}
                          </Link>
                        ))}
                      </div>
                      {serie && !serie.ok && <p className="text-sm text-pop-danger">{serie.erreur}</p>}
                      {serie?.ok && (
                        <>
                          <CourbeSerie
                            titre={`${LIBELLES_INDICATEUR[serie.donnees.indicateur] ?? serie.donnees.indicateur} — ${serie.donnees.agence ?? "MICROPOP"}`}
                            points={serie.donnees.points}
                            unite={serie.donnees.points[0]?.unite ?? null}
                          />
                          <details>
                            <summary className="cursor-pointer text-sm text-pop-bleu-2">Voir les valeurs</summary>
                            <table className="mt-2 text-sm">
                              <tbody>
                                {serie.donnees.points.map((p) => (
                                  <tr key={p.date} className="border-b border-pop-bord/60">
                                    <td className="py-1 pr-6 text-pop-gris">{p.date}</td>
                                    <td className="chiffres py-1 pr-6 text-right text-pop-encre">
                                      {p.unite === "%" ? `${p.valeur.toFixed(2)} %` : montant(p.valeur)}
                                    </td>
                                    <td className="py-1 text-xs text-pop-gris">
                                      {p.source === "calcul_poppilot" ? "calcul PopPilot" : "historique importe"}
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </details>
                        </>
                      )}
                    </section>
                  )}
                  {catalogue.donnees.indicateurs.length === 0 && (
                    <p className="text-sm text-pop-gris">
                      Aucune serie pour l&apos;instant : calculer les arretes charges ou importer un historique.
                    </p>
                  )}
                  {ecriture && (
                    <section className="rounded-2xl border border-pop-bord bg-pop-carte p-5 shadow-sm">
                      <FormulairesSeries nonAlimentes={catalogue.donnees.arretes_non_alimentes} />
                    </section>
                  )}
                </>
              )}
            </>
          )}
        </div>
      </Coquille>
    </FournisseurSession>
  );
}
