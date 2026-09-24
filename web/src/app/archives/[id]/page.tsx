/**
 * PopPilot — edition en ligne d'une archive tableur (GET /archives/{id}/donnees).
 * La grille = fichier depose + modifications tracees. Le fichier depose reste
 * intact ; « Telecharger la version modifiee » rend la grille en .xlsx.
 */
import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { Coquille } from "@/composants/Coquille";
import { FournisseurSession } from "@/composants/ContexteSession";
import { EditeurArchive } from "@/composants/EditeurArchive";
import { sessionCourante } from "@/lib/session";
import { aAccesTotal, peutEcrire } from "@/lib/roles";
import { appelerApi } from "@/lib/api";
import type { DonneesArchive } from "@/lib/archives";

export const metadata: Metadata = { title: "Edition d'archive — PopPilot" };
export const dynamic = "force-dynamic";

export default async function PageEditionArchive({ params }: { params: Promise<{ id: string }> }) {
  const { profil, jeton, avertissement } = await sessionCourante();
  if (profil === null) {
    if (avertissement) redirect("/login");
    redirect("/login?suite=/archives");
  }
  if (!aAccesTotal(profil)) redirect("/credit");
  const { id } = await params;
  if (!/^\d+$/.test(id)) redirect("/archives");

  const d = profil.demo ? null : await appelerApi<DonneesArchive>(`/archives/${id}/donnees`, jeton);

  return (
    <FournisseurSession profil={profil}>
      <Coquille profil={profil} actif="/archives">
        <div className="space-y-4">
          <Link href="/archives" className="lien-pop text-sm">
            ← Bibliotheque
          </Link>
          {d === null ? (
            <p className="text-sm text-pop-gris">Indisponible en demonstration.</p>
          ) : !d.ok ? (
            <p role="alert" className="text-sm text-pop-danger">{d.erreur}</p>
          ) : (
            <>
              <header className="flex flex-wrap items-end justify-between gap-3">
                <div>
                  <h1 className="text-2xl font-semibold tracking-tight text-pop-encre">
                    {d.donnees.archive.titre}{" "}
                    <span className="text-base font-normal text-pop-gris">v{d.donnees.archive.version}</span>
                  </h1>
                  <p className="text-xs text-pop-gris">
                    {d.donnees.nb_modifications} modification(s) enregistree(s)
                    {d.donnees.derniere_modification &&
                      ` · derniere par ${d.donnees.derniere_modification.par} le ${d.donnees.derniere_modification.le.slice(0, 16).replace("T", " ")}`}
                    . Le fichier depose n&apos;est jamais modifie.
                  </p>
                </div>
                <div className="flex gap-3 text-sm">
                  <a href={`/api/archives/${id}?modifie=1`} className="lien-pop font-medium">
                    Telecharger la version modifiee
                  </a>
                  <a href={`/api/archives/${id}`} className="lien-pop">
                    Fichier d&apos;origine
                  </a>
                </div>
              </header>
              <EditeurArchive
                key={d.donnees.nb_modifications}
                archiveId={d.donnees.archive.id}
                grille={d.donnees.grille}
                modifiable={peutEcrire(profil)}
              />
            </>
          )}
        </div>
      </Coquille>
    </FournisseurSession>
  );
}
