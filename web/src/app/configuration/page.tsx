/**
 * PopPilot — CONFIGURATION DE L'ARRETE (saisie manuelle DAF / CDG).
 *
 * Reunit en un seul ecran tout ce qui ne se calcule pas et doit etre SAISI :
 * le taux de change BCC, la provision speciale des agences fermees, la grille
 * de reintegrations fiscales, le mapping budgetaire et le referentiel des
 * agences. Ces valeurs sont persistees dans Supabase par l'API, et relues par
 * les moteurs au calcul suivant — rien n'est garde cote navigateur.
 *
 * ROLES : reserve a DIRECTION et CDG (ROLES_ECRITURE). L'AUDIT a un acces
 * total en LECTURE sur les chiffres, mais ne parametre rien : un controleur ne
 * remplit pas ce qu'il controle.
 *
 * L'ARRETE COURANT compte : la provision manuelle est attachee a UN arrete
 * precis. Le selecteur en haut de page gouverne cette section ; le taux, les
 * reintegrations, le mapping et les agences sont, eux, versionnes a date
 * d'effet et valent au-dela d'un seul arrete.
 */
import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { Coquille } from "@/composants/Coquille";
import { FournisseurSession } from "@/composants/ContexteSession";
import { SelecteurArrete } from "@/composants/SelecteurArrete";
import { PanneauConfiguration } from "@/composants/PanneauConfiguration";
import { sessionCourante } from "@/lib/session";
import { chargerConfiguration, refusConfiguration } from "@/lib/configuration-serveur";
import { ARRETE_PAR_DEFAUT } from "@/lib/credit";
import { dateArreteValide, dateLongue } from "@/lib/format";

export const metadata: Metadata = {
  title: "Configuration — PopPilot",
  description: "Taux de change, provisions manuelles, reintegrations, mapping, agences.",
};

export const dynamic = "force-dynamic";

export default async function PageConfiguration({
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
    redirect("/login?suite=/configuration");
  }

  const { arrete: demande } = await searchParams;
  const arrete =
    typeof demande === "string" && dateArreteValide(demande) ? demande : ARRETE_PAR_DEFAUT;

  const refus = refusConfiguration(profil);
  if (refus !== null) {
    return (
      <FournisseurSession profil={profil}>
        <Coquille profil={profil} actif="/configuration">
          <div className="max-w-2xl space-y-4">
            <h1 className="text-2xl font-semibold tracking-tight text-pop-encre">
              Configuration
            </h1>
            <div className="rounded-xl border border-pop-bord bg-pop-carte px-5 py-4 shadow-sm">
              <p className="text-[13px] font-semibold text-pop-encre">
                Ecran reserve aux roles qui alimentent le socle
              </p>
              <p className="mt-1.5 text-[13px] leading-relaxed text-pop-gris">{refus}</p>
            </div>
          </div>
        </Coquille>
      </FournisseurSession>
    );
  }

  const tableau = await chargerConfiguration(arrete, jeton);

  const erreurs = [
    tableau.erreurParametres && `Parametres de l'arrete : ${tableau.erreurParametres}`,
    tableau.erreurMapping && `Mapping budgetaire : ${tableau.erreurMapping}`,
    tableau.erreurAgences && `Referentiel des agences : ${tableau.erreurAgences}`,
  ].filter((m): m is string => Boolean(m));

  return (
    <FournisseurSession profil={profil}>
      <Coquille profil={profil} actif="/configuration">
        <div className="space-y-6">
          <header>
            <h1 className="text-2xl font-semibold tracking-tight text-pop-encre">
              Configuration
            </h1>
            <p className="mt-1 text-sm text-pop-gris">
              Les intrants qui ne se calculent pas et qui pesent sur tous les ecrans.
              Arrete courant&nbsp;: {dateLongue(tableau.arrete)}.
            </p>
          </header>

          <SelecteurArrete key={tableau.arrete} arrete={tableau.arrete} />

          {/* Chaque section manquante est nommee : une section vide sans message
              ferait croire qu'il n'y a rien a parametrer. */}
          {erreurs.length > 0 && (
            <div className="rounded-xl border border-pop-danger/30 bg-pop-danger/5 px-4 py-3 text-sm text-pop-danger">
              <p className="font-semibold">
                {erreurs.length === 1
                  ? "Une section n'a pas pu etre chargee."
                  : `${erreurs.length} sections n'ont pas pu etre chargees.`}
              </p>
              <ul className="mt-1 space-y-0.5 text-[13px] leading-relaxed">
                {erreurs.map((m) => (
                  <li key={m}>{m}</li>
                ))}
              </ul>
            </div>
          )}

          <PanneauConfiguration
            arrete={tableau.arrete}
            parametres={tableau.parametres}
            mapping={tableau.mapping}
            agences={tableau.agences?.agences ?? []}
          />
        </div>
      </Coquille>
    </FournisseurSession>
  );
}
