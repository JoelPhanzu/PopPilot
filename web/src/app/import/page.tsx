/**
 * PopPilot — ecran IMPORT : charger les fichiers du CBS dans le socle.
 *
 * C'est le point d'entree de toute la plateforme : tant qu'aucune extraction
 * n'est chargee, chaque tableau de bord affiche « aucune donnee pour cet
 * arrete ». L'ecran appelle GET /import/domaines pour savoir ce que l'API
 * accepte, POST /import/{domaine} pour envoyer, GET /imports pour montrer ce
 * que la base contient deja.
 *
 * Cloisonnement : reserve a DIRECTION / CDG (ROLES_ECRITURE, miroir de l'API).
 * L'AUDIT et les agences n'y ont pas acces — l'API les refuserait de toute
 * facon, cette page ne fait que ne pas le leur proposer.
 */
import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { Coquille } from "@/composants/Coquille";
import { ExportSections } from "@/composants/ExportSections";
import { FournisseurSession } from "@/composants/ContexteSession";
import { sessionCourante } from "@/lib/session";
import { peutEcrire } from "@/lib/roles";
import { chargerCatalogue, chargerJournal } from "@/lib/import-serveur";
import { FormulaireImport } from "./FormulaireImport";

export const metadata: Metadata = {
  title: "Import CBS — PopPilot",
  description: "Charger les extractions du CBS dans le socle de donnees.",
};

/** L'etat de la base change a chaque import : jamais de rendu mis en cache. */
export const dynamic = "force-dynamic";

function horodatageLisible(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime())
    ? iso
    : d.toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "short" });
}

export default async function PageImport() {
  const { profil, jeton, avertissement } = await sessionCourante();

  if (profil === null) {
    if (avertissement) {
      return (
        <main className="flex min-h-dvh items-center justify-center bg-pop-bleu px-4">
          <div className="max-w-md rounded-2xl bg-white p-7 shadow-2xl">
            <h1 className="text-lg font-semibold text-pop-encre">Acces impossible</h1>
            <p className="mt-2 text-sm leading-relaxed text-pop-gris">{avertissement}</p>
            <a href="/login" className="lien-pop mt-4 inline-block text-sm font-medium">
              Retour a la connexion
            </a>
          </div>
        </main>
      );
    }
    redirect("/login?suite=/import");
  }

  // Un role sans droit d'ecriture n'a rien a faire ici : on le renvoie vers ce
  // qu'il a le droit de consulter, plutot que d'afficher un formulaire mort.
  if (!peutEcrire(profil)) redirect("/credit");

  const [catalogue, journal] = await Promise.all([
    chargerCatalogue(jeton),
    chargerJournal(jeton, 15),
  ]);

  return (
    <FournisseurSession profil={profil}>
      <Coquille profil={profil} actif="/import">
        <div className="space-y-6">
          <header>
            <h1 className="text-2xl font-semibold tracking-tight text-pop-encre">
              Import des fichiers du CBS
            </h1>
            <p className="mt-1 text-sm leading-relaxed text-pop-gris">
              Les fichiers sont confies tels quels aux moteurs d&apos;ingestion valides.
              Rien n&apos;est recalcule ici&nbsp;: la plateforme stocke des faits dates, les
              indicateurs sont derives ensuite.
            </p>
          </header>

          {/* En demonstration il n'y a ni jeton ni base : le dire, plutot que de laisser
              l'ecran annoncer une API muette alors qu'elle se porte tres bien. */}
          {profil.demo ? (
            <div
              role="alert"
              className="rounded-xl border border-pop-alerte/30 bg-pop-alerte/5 px-4 py-3 text-sm text-pop-alerte"
            >
              <p className="font-semibold">Import indisponible en mode demonstration.</p>
              <p className="mt-1 text-[13px] leading-relaxed">
                La demonstration n&apos;a pas de base a alimenter. Renseigner
                <code className="mx-1 rounded bg-white/70 px-1 py-0.5">web/.env.local</code> et
                <code className="mx-1 rounded bg-white/70 px-1 py-0.5">api/.env</code>, puis se
                connecter avec un compte reel.
              </p>
            </div>
          ) : catalogue.ok ? (
            <>
              <p className="text-xs text-pop-gris">
                Base alimentee&nbsp;: <span className="font-medium">{catalogue.donnees.base}</span>
              </p>

              <section className="rounded-2xl border border-pop-bord bg-pop-carte p-5 shadow-sm lg:p-6">
                <FormulaireImport
                  domaines={catalogue.donnees.domaines}
                  tailleMaxMo={catalogue.donnees.taille_max_mo}
                />
              </section>
            </>
          ) : (
            <div
              role="alert"
              className="rounded-xl border border-pop-danger/30 bg-pop-danger/5 px-4 py-3 text-sm text-pop-danger"
            >
              <p className="font-semibold">
                Aucun import possible&nbsp;: l&apos;API n&apos;a pas repondu.
              </p>
              <p className="mt-1 text-[13px] leading-relaxed">{catalogue.erreur}</p>
              <p className="mt-1 text-[13px] leading-relaxed">
                Le formulaire n&apos;est pas affiche tant que l&apos;API ne dit pas ce
                qu&apos;elle accepte&nbsp;: mieux vaut aucun envoi qu&apos;un envoi qui
                n&apos;arrivera nulle part.
              </p>
            </div>
          )}

          <section className="rounded-2xl border border-pop-bord bg-pop-carte p-5 shadow-sm lg:p-6">
            <h2 className="text-lg font-semibold text-pop-encre">Derniers imports</h2>
            <p className="mt-1 text-sm text-pop-gris">
              Ce que la base contient reellement, et qui l&apos;y a mis.
            </p>

            {profil.demo ? (
              <p className="mt-4 text-sm text-pop-gris">
                Aucun journal en demonstration.
              </p>
            ) : !journal.ok ? (
              <p className="mt-4 text-sm text-pop-danger">{journal.erreur}</p>
            ) : journal.donnees.imports.length === 0 ? (
              <p className="mt-4 text-sm text-pop-gris">
                Aucun import enregistre&nbsp;: le socle est vide. C&apos;est la raison pour
                laquelle les tableaux de bord n&apos;affichent encore aucun chiffre.
              </p>
            ) : (
              <div className="mt-4 overflow-x-auto">
                <div className="mb-3">
                  <ExportSections
                    titre="Journal des imports"
                    sousTitre={`Base : ${journal.donnees.base}`}
                    nom="PopPilot_journal_imports"
                    sections={[{
                      colonnes: [
                        { libelle: "Domaine", cle: "domaine" }, { libelle: "Arrete", cle: "date_arrete" },
                        { libelle: "Fichier", cle: "fichier" }, { libelle: "Lignes", cle: "acceptees" },
                        { libelle: "Rejetees", cle: "rejetees" }, { libelle: "Charge le", cle: "horodatage" },
                        { libelle: "Message", cle: "message" },
                      ],
                      lignes: journal.donnees.imports,
                    }]}
                  />
                </div>
                <table className="w-full min-w-[46rem] border-collapse text-sm">
                  <thead>
                    <tr className="border-b border-pop-bord text-left text-xs uppercase tracking-wide text-pop-gris">
                      <th className="py-2 pr-4 font-medium">Domaine</th>
                      <th className="py-2 pr-4 font-medium">Arrete</th>
                      <th className="py-2 pr-4 font-medium">Fichier</th>
                      <th className="py-2 pr-4 text-right font-medium">Lignes</th>
                      <th className="py-2 pr-4 text-right font-medium">Rejetees</th>
                      <th className="py-2 font-medium">Charge le</th>
                    </tr>
                  </thead>
                  <tbody>
                    {journal.donnees.imports.map((l, i) => (
                      <tr key={`${l.domaine}-${l.horodatage}-${i}`} className="border-b border-pop-bord/60">
                        <td className="py-2 pr-4 font-medium text-pop-encre">{l.domaine}</td>
                        <td className="py-2 pr-4 text-pop-gris">{l.date_arrete ?? "—"}</td>
                        <td className="py-2 pr-4 text-pop-gris" title={l.message ?? undefined}>
                          {l.fichier}
                        </td>
                        <td className="chiffres py-2 pr-4 text-right text-pop-encre">
                          {l.acceptees.toLocaleString("fr-FR")}
                        </td>
                        <td
                          className={
                            l.rejetees > 0
                              ? "chiffres py-2 pr-4 text-right font-medium text-pop-alerte"
                              : "chiffres py-2 pr-4 text-right text-pop-gris"
                          }
                        >
                          {l.rejetees.toLocaleString("fr-FR")}
                        </td>
                        <td className="py-2 text-pop-gris">{horodatageLisible(l.horodatage)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </div>
      </Coquille>
    </FournisseurSession>
  );
}
