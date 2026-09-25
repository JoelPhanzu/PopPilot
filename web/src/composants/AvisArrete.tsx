/**
 * PopPilot — avis de la regle du calendrier : la date choisie n'a pas d'arrete
 * enregistre, l'ecran montre (et le calendrier affiche) le dernier arrete enregistre
 * a cette date. Voir `lib/arretes.ts`.
 */
import { dateLongue } from "@/lib/format";
import type { ArreteResolu } from "@/lib/arretes";

export function AvisArrete({ resolu }: { resolu: ArreteResolu | null }) {
  if (!resolu?.demande || !resolu.arrete) return null;
  const avant = resolu.arrete < resolu.demande;
  return (
    <p role="status" className="text-sm text-pop-gris print:hidden">
      Aucun arrete enregistre au {dateLongue(resolu.demande)} : chiffres du{" "}
      {avant ? "dernier arrete enregistre a cette date" : "premier arrete enregistre"}, le{" "}
      <strong className="text-pop-encre">{dateLongue(resolu.arrete)}</strong>.
    </p>
  );
}
