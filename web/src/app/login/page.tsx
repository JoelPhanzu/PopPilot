/**
 * PopPilot — ecran de connexion (guide § interface, page 7 §4.2).
 *
 * Fond bleu MICROPOP, carte blanche centree, logo et signature de marque.
 * Le cyan #00AEEA n'apparait qu'en accent (filet, focus, liens) : en aplat il
 * ne tient pas le contraste, la charte l'interdit sur les grandes surfaces.
 */
import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { Logo, Signature } from "@/composants/Logo";
import { FormulaireConnexion } from "./FormulaireConnexion";
import { entrerEnDemonstration } from "./actions";
import { configurationAFaire, modeDemoAutorise, supabaseConfigure } from "@/lib/config";
import { sessionCourante } from "@/lib/session";
import { LIBELLES_ROLE, ROLES } from "@/lib/roles";

export const metadata: Metadata = {
  title: "Connexion — PopPilot",
  description: "Acces a la plateforme de pilotage MICROPOP.",
};

/** N'accepte qu'un chemin interne : une URL absolue ferait une redirection ouverte. */
function destination(suite: string | undefined): string {
  if (typeof suite === "string" && /^\/(?!\/)/.test(suite)) return suite;
  return "/credit";
}

export default async function PageConnexion({
  searchParams,
}: {
  searchParams: Promise<{ suite?: string }>;
}) {
  const { profil } = await sessionCourante();
  const { suite } = await searchParams;
  const apres = destination(suite);

  if (profil !== null) redirect(apres);

  const aConfigurer = configurationAFaire();
  const demo = modeDemoAutorise();

  return (
    <main className="relative flex min-h-dvh flex-col items-center justify-center overflow-hidden bg-pop-bleu px-4 py-10">
      {/* Halo discret : degrade bleu principal → bleu secondaire, sans aplat cyan. */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(90rem_45rem_at_50%_-10%,#1b5e86_0%,transparent_60%)]"
      />

      <div className="relative w-full max-w-[26rem]">
        <header className="mb-7 flex flex-col items-center text-center">
          <Logo taille={64} className="shadow-lg shadow-black/20" />
          <h1 className="mt-4 text-3xl font-semibold tracking-tight text-white">PopPilot</h1>
          <p className="mt-1.5 text-sm text-white/70">Plateforme de pilotage MICROPOP</p>
        </header>

        <section className="rounded-2xl bg-white p-7 shadow-2xl shadow-black/25">
          {/* Filet cyan : le seul aplat de cyan tolere — 3 px de haut. */}
          <div className="mb-6 h-[3px] w-12 rounded-full bg-pop-cyan" aria-hidden />
          <h2 className="text-lg font-semibold text-pop-encre">Connexion</h2>
          <p className="mt-1 mb-6 text-sm text-pop-gris">
            Identifiez-vous avec votre compte MICROPOP.
          </p>

          {aConfigurer !== null && (
            <p className="mb-5 rounded-lg border border-pop-alerte/30 bg-pop-alerte/5 px-3.5 py-3 text-sm text-pop-alerte">
              <span className="font-semibold">Supabase n&apos;est pas configure.</span>
              <br />
              {aConfigurer}
            </p>
          )}

          <FormulaireConnexion suite={apres} />

          {demo && (
            <div className="mt-7 border-t border-pop-bord pt-5">
              <p className="text-sm font-medium text-pop-encre">
                Parcourir sans compte (mode demonstration)
              </p>
              <p className="mt-1 text-xs leading-relaxed text-pop-gris">
                Donnees d&apos;illustration, pour verifier l&apos;interface et le cloisonnement
                par role. Ce mode disparait des que Supabase est configure et n&apos;existe
                jamais en production.
              </p>
              <div className="mt-3 grid grid-cols-2 gap-2">
                {ROLES.map((role) => (
                  <form key={role} action={entrerEnDemonstration}>
                    <input type="hidden" name="role" value={role} />
                    <button
                      type="submit"
                      className="w-full rounded-lg border border-pop-bord px-3 py-2 text-xs font-medium text-pop-gris
                                 transition hover:border-pop-cyan hover:text-pop-bleu-2
                                 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-pop-cyan"
                    >
                      {LIBELLES_ROLE[role]}
                    </button>
                  </form>
                ))}
              </div>
            </div>
          )}

          {!demo && !supabaseConfigure() && (
            <p className="mt-6 text-xs text-pop-gris">
              Renseignez <code className="rounded bg-pop-fond px-1 py-0.5">web/.env.local</code>{" "}
              puis relancez <code className="rounded bg-pop-fond px-1 py-0.5">npm run dev</code>.
            </p>
          )}
        </section>

        <footer className="mt-7 text-center">
          <Signature className="text-sm text-pop-cyan" />
          <p className="mt-1.5 text-xs text-white/50">
            MICROPOP &middot; Republique Democratique du Congo
          </p>
        </footer>
      </div>
    </main>
  );
}
