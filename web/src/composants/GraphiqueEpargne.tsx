"use client";

/**
 * PopPilot — comparaison des lignes du tableau de bord EPARGNE sur l'indicateur
 * choisi (encours, depots, retraits, collecte nette, couverture du credit,
 * croissance). Barres horizontales, une seule serie ; valeurs signees de part et
 * d'autre d'un zero. Survol / focus : detail. Clic sur une agence : filtre
 * l'ecran sur elle (l'URL change, tout se recalcule).
 */
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { entier, montant, pourcent } from "@/lib/format";
import type { LigneEpargneTdb } from "@/lib/epargne-tdb";

type Mesure = { cle: string; libelle: string; valeur: (l: LigneEpargneTdb) => number | null; pct?: boolean; nombre?: boolean };

const MESURES: Mesure[] = [
  { cle: "encours", libelle: "Encours (USD)", valeur: (l) => l.encours },
  { cle: "depots", libelle: "Depots de la periode", valeur: (l) => l.depots },
  { cle: "retraits", libelle: "Retraits de la periode", valeur: (l) => l.retraits },
  { cle: "collecte_nette", libelle: "Collecte nette", valeur: (l) => l.collecte_nette },
  { cle: "couverture", libelle: "Couverture du credit (%)", valeur: (l) => (l.couverture_credit == null ? null : l.couverture_credit * 100), pct: true },
  { cle: "croissance", libelle: "Croissance vs M-1 (%)", valeur: (l) => (l.croissance == null ? null : l.croissance * 100), pct: true },
  { cle: "epargnants", libelle: "Epargnants", valeur: (l) => l.nb_epargnants, nombre: true },
];

export function GraphiqueEpargne({ lignes, cliquable }: { lignes: LigneEpargneTdb[]; cliquable: boolean }) {
  const router = useRouter();
  const parametres = useSearchParams();
  const [cle, setCle] = useState("encours");
  const [survol, setSurvol] = useState<string | null>(null);
  const disponibles = MESURES.filter((m) => lignes.some((l) => m.valeur(l) != null));
  const m = disponibles.find((x) => x.cle === cle) ?? disponibles[0];
  if (!m || lignes.length < 2) return null;

  const points = lignes
    .map((l) => ({ l, v: m.valeur(l) }))
    .filter((p): p is { l: LigneEpargneTdb; v: number } => p.v != null)
    .sort((a, b) => b.v - a.v);
  const max = Math.max(0, ...points.map((p) => p.v));
  const min = Math.min(0, ...points.map((p) => p.v));
  const etendue = max - min || 1;
  const zero = (-min / etendue) * 72;
  const fmt = (v: number) => (m.pct ? pourcent(v) : m.nombre ? entier(v) : montant(v));

  function filtrer(agence: string | null) {
    if (!cliquable || !agence) return;
    const q = new URLSearchParams(parametres.toString());
    q.set("agence", agence);
    router.push(`?${q.toString()}`);
  }

  return (
    <figure className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <figcaption className="text-sm font-semibold text-pop-encre">Comparaison : {m.libelle}</figcaption>
        <select
          value={m.cle}
          onChange={(e) => setCle(e.target.value)}
          aria-label="Indicateur compare"
          className="rounded-lg border border-pop-bord bg-white px-2 py-1 text-xs text-pop-encre"
        >
          {disponibles.map((x) => (
            <option key={x.cle} value={x.cle}>
              {x.libelle}
            </option>
          ))}
        </select>
      </div>
      <ul className="space-y-1.5">
        {points.map(({ l, v }) => {
          const debut = v >= 0 ? zero : zero - (Math.abs(v) / etendue) * 72;
          const largeur = (Math.abs(v) / etendue) * 72;
          const actif = survol === l.designation;
          return (
            <li key={l.designation}>
              <button
                type="button"
                onClick={() => filtrer(l.cle)}
                onMouseEnter={() => setSurvol(l.designation)}
                onMouseLeave={() => setSurvol(null)}
                onFocus={() => setSurvol(l.designation)}
                onBlur={() => setSurvol(null)}
                className={`grid w-full grid-cols-[minmax(7rem,11rem)_1fr] items-center gap-2 rounded text-left ${cliquable ? "cursor-pointer" : "cursor-default"}`}
                title={cliquable ? `Filtrer sur ${l.designation}` : undefined}
              >
                <span className="truncate text-xs text-pop-encre">{l.designation}</span>
                <span className="relative h-5">
                  <span
                    className={`absolute top-0.5 h-4 rounded-sm ${v < 0 ? "bg-pop-danger/70" : "bg-pop-bleu-2"} ${actif ? "opacity-100" : "opacity-85"}`}
                    style={{ left: `${debut}%`, width: `${Math.max(largeur, 0.4)}%` }}
                  />
                  <span
                    className="chiffres absolute top-0 text-[11px] text-pop-encre"
                    style={{ left: `${Math.min(debut + largeur, 72) + 1}%` }}
                  >
                    {fmt(v)}
                  </span>
                </span>
              </button>
              {actif && (
                <p className="ml-[7.5rem] text-[11px] text-pop-gris">
                  Encours {montant(l.encours)} · depots {montant(l.depots)} · retraits {montant(l.retraits)} ·{" "}
                  {entier(l.nb_epargnants)} epargnants · {entier(l.nb_comptes)} comptes
                </p>
              )}
            </li>
          );
        })}
      </ul>
    </figure>
  );
}
