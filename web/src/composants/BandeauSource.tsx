/**
 * PopPilot — bandeau de provenance des chiffres.
 *
 * Regle de la maison : un chiffre affiche doit toujours dire d'ou il vient. Ce
 * bandeau distingue trois etats — donnees du socle via l'API, donnees
 * d'illustration, ou API muette — pour qu'une capture d'ecran ne puisse jamais
 * faire passer une demonstration pour un arrete reel.
 */
import type { SourceDonnees } from "@/lib/credit";

export function BandeauSource({
  source,
  erreurApi,
}: {
  source: SourceDonnees;
  erreurApi: string | null;
}) {
  if (source === "demonstration") {
    return (
      <div className="rounded-xl border border-pop-alerte/30 bg-pop-alerte/5 px-4 py-3 text-sm text-pop-alerte">
        <p className="font-semibold">Donnees de demonstration — aucun chiffre officiel.</p>
        <p className="mt-1 text-[13px] leading-relaxed">
          L&apos;API n&apos;a pas repondu, l&apos;ecran est alimente par des donnees
          d&apos;illustration. Pour les vrais chiffres&nbsp;:{" "}
          <code className="rounded bg-white/70 px-1 py-0.5">cd api &amp;&amp; uvicorn main:app --reload</code>
          {erreurApi && <span className="block mt-1 opacity-80">Detail&nbsp;: {erreurApi}</span>}
        </p>
      </div>
    );
  }

  if (erreurApi !== null) {
    return (
      <div className="rounded-xl border border-pop-danger/30 bg-pop-danger/5 px-4 py-3 text-sm text-pop-danger">
        <p className="font-semibold">Aucun chiffre affiche&nbsp;: l&apos;API n&apos;a pas repondu.</p>
        <p className="mt-1 text-[13px] leading-relaxed">{erreurApi}</p>
        <p className="mt-1 text-[13px] leading-relaxed">
          Un ecran vide vaut mieux qu&apos;un chiffre invente&nbsp;: rien n&apos;est estime ici.
        </p>
      </div>
    );
  }

  return null;
}
