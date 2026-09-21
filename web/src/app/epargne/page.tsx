/**
 * PopPilot — tableau de bord EPARGNE (Phase Epargne).
 *
 * Appelle GET /epargne?arrete=… sur l'API FastAPI, qui expose
 * `engine/epargne.py` (valide contre l'inventaire depot : 169 799 comptes,
 * 67 147 epargnants ≈ reference FINA 67 120). Aucun montant n'est recalcule
 * ici — la seule division faite a l'ecran est le solde moyen par epargnant,
 * et elle est nommee comme telle.
 *
 * Le point de vigilance de cet ecran est l'UNITE. Le moteur renvoie des
 * montants convertis (homogenes, sommables) ET des montants en devise
 * d'origine (non sommables entre eux). Les deux ne se cotoient jamais dans un
 * meme tableau : la ventilation par type est en USD converti, la ventilation
 * par devise reste en devise d'emission et n'a aucun total general.
 */
import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { Coquille } from "@/composants/Coquille";
import { FournisseurSession } from "@/composants/ContexteSession";
import { CarteIndicateur } from "@/composants/CarteIndicateur";
import { SelecteurArrete } from "@/composants/SelecteurArrete";
import { BandeauSource } from "@/composants/BandeauSource";
import { BoutonExport } from "@/composants/BoutonExport";
import { VentilationEpargne } from "@/composants/VentilationEpargne";
import { TableauEpargneDevises } from "@/composants/TableauEpargneDevises";
import { sessionCourante } from "@/lib/session";
import { chargerEpargne, refusEpargne } from "@/lib/epargne-serveur";
import { soldeMoyen } from "@/lib/epargne";
import { ARRETE_PAR_DEFAUT } from "@/lib/credit";
import { dateArreteValide, dateLongue, entier, montant, part, pourcent } from "@/lib/format";

export const metadata: Metadata = {
  title: "Epargne — PopPilot",
  description: "Encours epargne, ventilation par type de depot et par devise.",
};

export const dynamic = "force-dynamic";

export default async function PageEpargne({
  searchParams,
}: {
  searchParams: Promise<{ arrete?: string }>;
}) {
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
    redirect("/login?suite=/epargne");
  }

  const { arrete: demande } = await searchParams;
  const arrete =
    typeof demande === "string" && dateArreteValide(demande) ? demande : ARRETE_PAR_DEFAUT;

  const refus = refusEpargne(profil);
  if (refus !== null) {
    return (
      <FournisseurSession profil={profil}>
        <Coquille profil={profil} actif="/epargne">
          <div className="max-w-2xl space-y-4">
            <h1 className="text-2xl font-semibold tracking-tight text-pop-encre">Epargne</h1>
            <div className="rounded-xl border border-pop-bord bg-pop-carte px-5 py-4 shadow-sm">
              <p className="text-[13px] font-semibold text-pop-encre">
                Domaine reserve aux roles d&apos;institution
              </p>
              <p className="mt-1.5 text-[13px] leading-relaxed text-pop-gris">{refus}</p>
              <a href="/credit" className="lien-pop mt-3 inline-block text-[13px] font-medium">
                Aller au tableau de bord credit
              </a>
            </div>
          </div>
        </Coquille>
      </FournisseurSession>
    );
  }

  const tableau = await chargerEpargne(arrete, profil, jeton);
  const e = tableau.donnees;

  const moyen = e === null ? null : soldeMoyen(e.encours_total, e.nb_epargnants);
  const partAVue = e === null ? null : part(e.depots_a_vue, e.encours_total);
  const partGroupe = e === null ? null : part(e.epargne_groupe, e.encours_total);
  const comptesParEpargnant =
    e === null || !e.nb_epargnants ? null : e.nb_comptes / e.nb_epargnants;

  return (
    <FournisseurSession profil={profil}>
      <Coquille profil={profil} actif="/epargne">
        <div className="space-y-6">
          <header className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <h1 className="text-2xl font-semibold tracking-tight text-pop-encre">Epargne</h1>
              <p className="mt-1 text-sm text-pop-gris">
                Arrete du {dateLongue(tableau.arrete)} &middot; MICROPOP, toutes agences
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <BoutonExport domaine="epargne" arrete={tableau.arrete} />
              <p className="text-xs text-pop-gris">
                Source&nbsp;:{" "}
                {tableau.source === "api"
                ? "moteur valide (GET /epargne)"
                : "donnees de demonstration"}
              </p>
            </div>
          </header>

          <SelecteurArrete key={tableau.arrete} arrete={tableau.arrete} />

          <BandeauSource source={tableau.source} erreurApi={tableau.erreurApi} />

          {e !== null && (
            <>
              <section
                aria-label="Chiffres cles"
                className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4"
              >
                <CarteIndicateur
                  vedette
                  accent
                  intitule="Encours epargne"
                  valeur={`${montant(e.encours_total)} USD`}
                  precision={`${entier(e.nb_comptes)} comptes · ${entier(e.nb_epargnants)} epargnants`}
                  note={
                    e.taux_change === null
                      ? "Aucun taux saisi pour cet arrete : les montants CDF n'ont pas pu etre ramenes en USD."
                      : `Total homogene : le CDF est converti au taux de l'arrete (${montant(e.taux_change)} CDF/USD).`
                  }
                />
                <CarteIndicateur
                  intitule="Depots a vue"
                  valeur={montant(e.depots_a_vue)}
                  precision={partAVue === null ? null : `${pourcent(partAVue)} de l'encours`}
                  note="Denominateur de la liquidite immediate (E4) : c'est cette ligne qui relie l'epargne aux indicateurs prudentiels."
                />
                <CarteIndicateur
                  intitule="Solde moyen par epargnant"
                  valeur={moyen === null ? "—" : montant(moyen)}
                  precision={
                    comptesParEpargnant === null
                      ? null
                      : `${comptesParEpargnant.toFixed(2).replace(".", ",")} compte(s) par epargnant`
                  }
                  note="Encours total divise par le nombre d'epargnants distincts — la seule division faite sur cet ecran."
                />
                <CarteIndicateur
                  intitule="Epargne des groupes"
                  valeur={montant(e.epargne_groupe)}
                  precision={partGroupe === null ? null : `${pourcent(partGroupe)} de l'encours`}
                  note="Transitoire Groupe + Caution Groupes, selon la classification tranchee par le CDG."
                />
              </section>

              <VentilationEpargne parType={e.par_type} total={e.encours_total} />

              <TableauEpargneDevises
                parTypeDevise={e.par_type_devise}
                parDeviseOrigine={e.par_devise_origine}
                taux={e.taux_change}
                encoursTotal={e.encours_total}
              />
            </>
          )}
        </div>
      </Coquille>
    </FournisseurSession>
  );
}
