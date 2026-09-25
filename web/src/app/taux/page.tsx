/**
 * PopPilot — taux de change USD/CDF enregistres, dans l'ordre CHRONOLOGIQUE.
 *
 * GET /taux?debut=&fin= : bornes incluses et facultatives. Le filtre vit dans l'URL,
 * et les boutons CSV / Excel / PDF reprennent ces memes parametres : le fichier
 * telecharge est exactement la liste affichee. Les taux s'enregistrent par la page
 * Import (domaine « Taux de change », fichier de la BCC) ou la page Configuration.
 */
import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { Coquille } from "@/composants/Coquille";
import { FournisseurSession } from "@/composants/ContexteSession";
import { BoutonsExportTableau } from "@/composants/BoutonsExportTableau";
import { sessionCourante } from "@/lib/session";
import { appelerApi } from "@/lib/api";
import { dateArreteValide, dateLongue, entier } from "@/lib/format";

export const metadata: Metadata = {
  title: "Taux de change — PopPilot",
  description: "Taux USD/CDF enregistres, filtrables par periode et telechargeables.",
};

export const dynamic = "force-dynamic";

type Reponse = { debut: string | null; fin: string | null; nombre: number; taux: { date: string; taux: number }[] };

// Les taux de la BCC portent jusqu'a 5 decimales : on les montre tels quels.
const TAUX = new Intl.NumberFormat("fr-FR", { minimumFractionDigits: 2, maximumFractionDigits: 5 });

const champ =
  "chiffres mt-1 rounded-lg border border-pop-bord bg-white px-3 py-1.5 text-sm text-pop-encre outline-none focus:border-pop-cyan focus:ring-2 focus:ring-pop-cyan/30";

/** 2026-09-24 → 24/09/2026 (sans passer par Date : pas de decalage de fuseau). */
function jjmmaaaa(iso: string): string {
  return `${iso.slice(8, 10)}/${iso.slice(5, 7)}/${iso.slice(0, 4)}`;
}

export default async function PageTaux({
  searchParams,
}: {
  searchParams: Promise<{ debut?: string; fin?: string }>;
}) {
  const { profil, jeton, avertissement } = await sessionCourante();
  if (profil === null) {
    if (avertissement) redirect("/login");
    redirect("/login?suite=/taux");
  }

  const sp = await searchParams;
  const debut = sp.debut && dateArreteValide(sp.debut) ? sp.debut : "";
  const fin = sp.fin && dateArreteValide(sp.fin) ? sp.fin : "";
  const q = new URLSearchParams();
  if (debut) q.set("debut", debut);
  if (fin) q.set("fin", fin);
  const r = profil.demo ? null : await appelerApi<Reponse>(`/taux?${q.toString()}`, jeton);

  const periode = debut || fin
    ? `du ${debut ? dateLongue(debut) : "premier taux"} au ${fin ? dateLongue(fin) : "dernier taux"}`
    : "tous les taux enregistres";

  return (
    <FournisseurSession profil={profil}>
      <Coquille profil={profil} actif="/taux">
        <div className="space-y-6">
          <header className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <h1 className="text-2xl font-semibold tracking-tight text-pop-encre">Taux de change USD/CDF</h1>
              <p className="mt-1 text-sm text-pop-gris">
                {periode} &middot; ordre chronologique &middot; source : fichier de la BCC importe ou saisie.
              </p>
            </div>
            {r?.ok && r.donnees.nombre > 0 && (
              <BoutonsExportTableau domaine="taux" parametres={{ debut, fin }} />
            )}
          </header>

          {/* Formulaire GET : le filtre part dans l'URL, l'ecran est partageable tel quel. */}
          <form method="get" className="flex flex-wrap items-end gap-4 rounded-xl border border-pop-bord bg-pop-carte px-4 py-3 shadow-sm print:hidden">
            <label className="block text-[12px] font-medium text-pop-gris">
              Date debut
              <input type="date" name="debut" defaultValue={debut} className={`${champ} block`} />
            </label>
            <label className="block text-[12px] font-medium text-pop-gris">
              Date fin
              <input type="date" name="fin" defaultValue={fin} className={`${champ} block`} />
            </label>
            <button type="submit" className="rounded-lg bg-pop-bleu px-4 py-2 text-sm font-medium text-white hover:bg-pop-bleu-2">
              Filtrer
            </button>
            {(debut || fin) && (
              <Link href="/taux" className="lien-pop text-sm">Tout afficher</Link>
            )}
          </form>

          {r === null ? (
            <p className="text-sm text-pop-gris">Indisponible en demonstration.</p>
          ) : !r.ok ? (
            <p role="alert" className="text-sm text-pop-danger">{r.erreur}</p>
          ) : r.donnees.nombre === 0 ? (
            <p className="text-sm text-pop-gris">
              Aucun taux enregistre sur cette periode. Importer le fichier de la BCC depuis la page Import
              (domaine « Taux de change »).
            </p>
          ) : (
            <section className="overflow-x-auto rounded-xl border border-pop-bord bg-pop-carte shadow-sm">
              <table className="w-full max-w-xl border-collapse text-sm">
                <caption className="px-4 py-2 text-left text-xs text-pop-gris">
                  {entier(r.donnees.nombre)} taux, du {jjmmaaaa(r.donnees.taux[0].date)} au{" "}
                  {jjmmaaaa(r.donnees.taux[r.donnees.taux.length - 1].date)}
                </caption>
                <thead className="bg-pop-bleu">
                  <tr>
                    <th className="px-4 py-2.5 text-left text-[12px] font-semibold uppercase tracking-wide text-white/90">Date</th>
                    <th className="px-4 py-2.5 text-right text-[12px] font-semibold uppercase tracking-wide text-white/90">Taux USD/CDF</th>
                  </tr>
                </thead>
                <tbody>
                  {r.donnees.taux.map((t) => (
                    <tr key={t.date} className="border-b border-pop-bord/60">
                      <td className="chiffres px-4 py-1.5 text-[13px] text-pop-encre">{jjmmaaaa(t.date)}</td>
                      <td className="chiffres px-4 py-1.5 text-right text-[13px] text-pop-encre">{TAUX.format(t.taux)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          )}
        </div>
      </Coquille>
    </FournisseurSession>
  );
}
