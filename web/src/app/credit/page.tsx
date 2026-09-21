/**
 * PopPilot — tableau de bord CREDIT (guide page 7 §4.3).
 *
 * Appelle GET /par?arrete=… (et GET /provisions?arrete=… pour les roles a acces
 * total) sur l'API FastAPI, qui expose les moteurs valides au centime. Aucun
 * indicateur n'est recalcule ici.
 *
 * Cloisonnement — trois verrous, dans cet ordre :
 *   1. RLS Supabase (acces directs a la base) ;
 *   2. filtre par agence dans l'API (api/auth_supabase.py) ;
 *   3. cette page : un role AGENCE ne voit QUE sa ligne, et le total affiche
 *      est la somme de ses seules lignes — jamais l'agregat institution.
 */
import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { Coquille } from "@/composants/Coquille";
import { FournisseurSession } from "@/composants/ContexteSession";
import { CarteIndicateur } from "@/composants/CarteIndicateur";
import { GraphiquePar } from "@/composants/GraphiquePar";
import { TableauAgences } from "@/composants/TableauAgences";
import { SelecteurArrete } from "@/composants/SelecteurArrete";
import { BandeauSource } from "@/composants/BandeauSource";
import { BoutonExport } from "@/composants/BoutonExport";
import { sessionCourante } from "@/lib/session";
import { chargerTableauCredit, ARRETE_PAR_DEFAUT } from "@/lib/credit";
import { aAccesTotal } from "@/lib/roles";
import { dateArreteValide, dateLongue, entier, montant, pourcent, part } from "@/lib/format";

export const metadata: Metadata = {
  title: "Credit — PopPilot",
  description: "PAR, provisions et encours par agence.",
};

/** Les chiffres dependent de la session : jamais de rendu statique mis en cache. */
export const dynamic = "force-dynamic";

export default async function PageCredit({
  searchParams,
}: {
  searchParams: Promise<{ arrete?: string }>;
}) {
  const { profil, jeton, avertissement } = await sessionCourante();

  if (profil === null) {
    // Un compte authentifie mais sans profil actif doit LIRE pourquoi il n'entre
    // pas ; le renvoyer en boucle vers /login n'expliquerait rien.
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
    redirect("/login?suite=/credit");
  }

  const { arrete: demande } = await searchParams;
  const arrete =
    typeof demande === "string" && dateArreteValide(demande) ? demande : ARRETE_PAR_DEFAUT;

  const tableau = await chargerTableauCredit(arrete, profil, jeton);
  const g = tableau.par.global;
  const agences = tableau.par.agences;
  const total = aAccesTotal(profil);

  // Taux : celui de l'API s'il existe, sinon derive du couple (montant, encours)
  // DEJA filtre. Jamais un pourcentage venu d'ailleurs.
  const tauxPar1 = g.pct_par1 ?? part(g.par1 ?? 0, g.encours ?? 0);
  const tauxPar30 = g.pct_par30 ?? part(g.par30 ?? 0, g.encours ?? 0);
  const tauxPar90 = g.pct_par90 ?? (g.par90 === undefined ? null : part(g.par90, g.encours ?? 0));

  const provisionTotale = tableau.provisions?.provision_capital_totale ?? null;
  const tauxProvision = provisionTotale === null ? null : part(provisionTotale, g.encours ?? 0);
  const vide = agences.length === 0 && g.encours === undefined;

  return (
    <FournisseurSession profil={profil}>
      <Coquille profil={profil} actif="/credit">
        <div className="space-y-6">
          <header className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <h1 className="text-2xl font-semibold tracking-tight text-pop-encre">
                Tableau de bord credit
              </h1>
              <p className="mt-1 text-sm text-pop-gris">
                Arrete du {dateLongue(tableau.arrete)} &middot;{" "}
                {total ? "MICROPOP, toutes agences" : `Agence ${profil.agence ?? "—"}`}
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <BoutonExport domaine="credit" arrete={tableau.arrete} />
              <p className="text-xs text-pop-gris">
                Source&nbsp;:{" "}
                {tableau.source === "api"
                ? "moteurs valides (GET /par, /provisions)"
                : "donnees de demonstration"}
              </p>
            </div>
          </header>

          <SelecteurArrete key={tableau.arrete} arrete={tableau.arrete} />

          <BandeauSource source={tableau.source} erreurApi={tableau.erreurApi} />

          {!vide && (
            <>
              {/* PAR1 au premier plan, a egalite avec PAR30 et PAR90 : c'est le
                  portefeuille a risque GLOBAL (tout credit a >= 1 jour de retard). */}
              <section
                aria-label="Indicateurs cles"
                className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4"
              >
                <CarteIndicateur
                  vedette
                  accent
                  intitule={total ? "Encours de credit" : `Encours — ${profil.agence ?? ""}`}
                  valeur={g.encours === undefined ? "—" : `${montant(g.encours)} USD`}
                  precision={
                    g.nb_credits === undefined
                      ? null
                      : `${entier(g.nb_credits)} credits${
                          g.nb_clients === undefined
                            ? ""
                            : ` · ${entier(g.nb_clients)} emprunteurs`
                        }`
                  }
                  note={
                    total
                      ? "Encours calcule une seule fois : c'est l'invariant qui rend tous les rapports coherents."
                      : "Perimetre limite a votre agence."
                  }
                />
                <CarteIndicateur
                  intitule="PAR1"
                  valeur={g.par1 === undefined ? "—" : montant(g.par1)}
                  precision={tauxPar1 === null ? null : `${pourcent(tauxPar1)} de l'encours`}
                  note="Portefeuille a risque global : tout credit a au moins 1 jour de retard."
                />
                <CarteIndicateur
                  intitule="PAR30"
                  valeur={g.par30 === undefined ? "—" : montant(g.par30)}
                  precision={tauxPar30 === null ? null : `${pourcent(tauxPar30)} de l'encours`}
                  note="Norme reglementaire BCC (retard >= 31 jours)."
                />
                <CarteIndicateur
                  intitule="PAR90"
                  valeur={g.par90 === undefined ? "—" : montant(g.par90)}
                  precision={tauxPar90 === null ? null : `${pourcent(tauxPar90)} de l'encours`}
                  note={
                    g.par90 === undefined
                      ? "Non renvoye par l'API pour ce perimetre."
                      : "Risque installe (retard >= 91 jours)."
                  }
                />
                <CarteIndicateur
                  intitule="Provisions"
                  valeur={provisionTotale === null ? "—" : montant(provisionTotale)}
                  precision={
                    tauxProvision === null ? null : `${pourcent(tauxProvision)} de l'encours`
                  }
                  note={
                    tableau.noteProvisions ??
                    "Bareme reglementaire + complements manuels valides par la DAF (agences fermees)."
                  }
                />
              </section>

              <GraphiquePar lignes={agences} />

              <TableauAgences
                lignes={agences}
                provisions={total ? tableau.provisions?.par_agence : null}
              />

              {!total && (
                <p className="text-xs leading-relaxed text-pop-gris">
                  Profil AGENCE&nbsp;: les agregats de l&apos;institution (total MICROPOP,
                  comptabilite, indicateurs prudentiels, provisions) ne sont ni affiches ni
                  demandes. Le cloisonnement est applique par le RLS Supabase et par
                  l&apos;API&nbsp;; cette page ne fait que s&apos;y conformer.
                </p>
              )}
            </>
          )}
        </div>
      </Coquille>
    </FournisseurSession>
  );
}
