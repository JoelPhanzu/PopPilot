/**
 * PopPilot — traitement du grand livre CBS pour SAGE (chantier 5).
 *
 * L'utilisateur ne fournit QUE l'extraction du CBS ; l'API rend le fichier au
 * format SAGE (engine/traitement_sage.py), converti au taux JOURNALIER lu dans
 * la plateforme. L'ecran n'applique aucune regle comptable.
 *
 * Reserve a DIRECTION / CDG (ROLES_ECRITURE, miroir de l'API).
 */
import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { Coquille } from "@/composants/Coquille";
import { ExportSections } from "@/composants/ExportSections";
import { FournisseurSession } from "@/composants/ContexteSession";
import { FormulaireSage } from "@/composants/FormulaireSage";
import { sessionCourante } from "@/lib/session";
import { peutEcrire } from "@/lib/roles";
import { appelerApi } from "@/lib/api";

export const metadata: Metadata = {
  title: "Traitement SAGE — PopPilot",
  description: "Grand livre CBS converti au format d'import SAGE.",
};

export const dynamic = "force-dynamic";

type Journal = {
  traitements: {
    date: string;
    periode: string | null;
    fichier: string | null;
    lignes: number | null;
    statut: string | null;
    message: string | null;
  }[];
};

const COULEUR_STATUT: Record<string, string> = {
  OK: "text-pop-ok",
  ALERTE: "text-pop-alerte",
  ECHEC: "text-pop-danger",
};

export default async function PageSage() {
  const { profil, jeton, avertissement } = await sessionCourante();
  if (profil === null) {
    if (avertissement) redirect("/login");
    redirect("/login?suite=/sage");
  }
  if (!peutEcrire(profil)) redirect("/credit");

  const journal = profil.demo ? null : await appelerApi<Journal>("/sage/journal?limite=15", jeton);

  return (
    <FournisseurSession profil={profil}>
      <Coquille profil={profil} actif="/sage">
        <div className="space-y-6">
          <header>
            <h1 className="text-2xl font-semibold tracking-tight text-pop-encre">
              Traitement du grand livre pour SAGE
            </h1>
            <p className="mt-1 max-w-3xl text-sm leading-relaxed text-pop-gris">
              Deposer l&apos;extraction du CBS&nbsp;: la plateforme rend le fichier a importer
              dans SAGE. Compte reformate sur 8 chiffres (suffixe 0 = USD, 1 = CDF), montants
              USD convertis au <strong>taux du jour</strong> de chaque ecriture, Type_Ecriture
              «&nbsp;G&nbsp;». N° piece, code journal et section restent vides&nbsp;: le
              comptable les renseigne avant l&apos;import.
            </p>
          </header>

          <FormulaireSage />

          <p className="text-xs leading-relaxed text-pop-gris">
            Un jour sans taux USD→CDF dans la plateforme bloque le traitement et la date est
            indiquee&nbsp;: saisir le taux (page Configuration) puis relancer. Le taux d&apos;un
            autre jour n&apos;est jamais utilise a sa place.
          </p>

          <section className="rounded-2xl border border-pop-bord bg-pop-carte p-5 shadow-sm lg:p-6">
            <h2 className="text-lg font-semibold text-pop-encre">Derniers traitements</h2>
            {journal === null ? (
              <p className="mt-3 text-sm text-pop-gris">Aucun journal en demonstration.</p>
            ) : !journal.ok ? (
              <p className="mt-3 text-sm text-pop-danger">{journal.erreur}</p>
            ) : journal.donnees.traitements.length === 0 ? (
              <p className="mt-3 text-sm text-pop-gris">Aucun traitement enregistre.</p>
            ) : (
              <div className="mt-4 overflow-x-auto">
                <div className="mb-3">
                  <ExportSections
                    titre="Journal des traitements SAGE"
                    nom="PopPilot_journal_sage"
                    sections={[{
                      colonnes: [
                        { libelle: "Date", cle: "date" }, { libelle: "Periode", cle: "periode" },
                        { libelle: "Fichier", cle: "fichier" }, { libelle: "Lignes", cle: "lignes" },
                        { libelle: "Statut", cle: "statut" }, { libelle: "Message", cle: "message" },
                      ],
                      lignes: journal.donnees.traitements,
                    }]}
                  />
                </div>
                <table className="w-full min-w-[40rem] border-collapse text-sm">
                  <thead>
                    <tr className="border-b border-pop-bord text-left text-xs uppercase tracking-wide text-pop-gris">
                      <th className="py-2 pr-4 font-medium">Date</th>
                      <th className="py-2 pr-4 font-medium">Periode</th>
                      <th className="py-2 pr-4 font-medium">Fichier</th>
                      <th className="py-2 pr-4 text-right font-medium">Lignes</th>
                      <th className="py-2 font-medium">Statut</th>
                    </tr>
                  </thead>
                  <tbody>
                    {journal.donnees.traitements.map((t, i) => (
                      <tr key={`${t.date}-${i}`} className="border-b border-pop-bord/60">
                        <td className="py-2 pr-4 text-pop-gris">{t.date}</td>
                        <td className="py-2 pr-4 text-pop-gris">{t.periode ?? "—"}</td>
                        <td className="py-2 pr-4 text-pop-encre" title={t.message ?? undefined}>
                          {t.fichier ?? "—"}
                        </td>
                        <td className="chiffres py-2 pr-4 text-right text-pop-encre">
                          {t.lignes?.toLocaleString("fr-FR") ?? "—"}
                        </td>
                        <td className={`py-2 font-medium ${COULEUR_STATUT[t.statut ?? ""] ?? ""}`}>
                          {t.statut ?? "—"}
                        </td>
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
