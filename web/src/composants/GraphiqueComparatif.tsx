"use client";

/**
 * PopPilot — comparaison des lignes du tableau de bord (agences, superviseurs ou
 * agents), sur l'indicateur CHOISI.
 *
 * Barres horizontales, une seule serie (#1B5E86) : la longueur code la valeur,
 * jamais le rang. Valeurs signees (croissance, cout du risque) : barres de part
 * et d'autre d'un zero trace. Etiquette de bout toujours lisible ; survol et
 * focus clavier donnent le detail ; un clic sur une agence FILTRE le tableau de
 * bord sur elle (l'URL change, tout se recalcule).
 */
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { entier, montant, pourcent } from "@/lib/format";
import type { LigneTdb } from "@/lib/credit-tdb";

type Mesure = { cle: string; libelle: string; valeur: (l: LigneTdb) => number | null; pct?: boolean; nombre?: boolean };

const MESURES: Mesure[] = [
  { cle: "encours", libelle: "Encours", valeur: (l) => l.encours },
  { cle: "pct_par30", libelle: "PAR30 (%)", valeur: (l) => l.pct_par30 * 100, pct: true },
  { cle: "pct_par1", libelle: "PAR1 (%)", valeur: (l) => l.pct_par1 * 100, pct: true },
  { cle: "decaisse_volume", libelle: "Volume decaisse (periode)", valeur: (l) => l.decaisse_volume },
  { cle: "decaisse_nombre", libelle: "Nombre decaisse (periode)", valeur: (l) => l.decaisse_nombre, nombre: true },
  { cle: "realisation", libelle: "Realisation objectif nombre (%)", valeur: (l) => (l.pct_realisation_nombre == null ? null : l.pct_realisation_nombre * 100), pct: true },
  { cle: "croissance", libelle: "Croissance vs M-1 (%)", valeur: (l) => (l.croissance == null ? null : l.croissance * 100), pct: true },
  { cle: "provisions", libelle: "Provisions", valeur: (l) => l.provisions },
  { cle: "cout_du_risque", libelle: "Cout du risque", valeur: (l) => l.cout_du_risque },
  { cle: "entree_par", libelle: "Entrees en PAR (montant)", valeur: (l) => l.entree_par_montant },
];

export function GraphiqueComparatif({ lignes, cliquable }: { lignes: LigneTdb[]; cliquable: boolean }) {
  const router = useRouter();
  const parametres = useSearchParams();
  const [cle, setCle] = useState("encours");
  const [survol, setSurvol] = useState<string | null>(null);
  const disponibles = MESURES.filter((m) => lignes.some((l) => m.valeur(l) != null));
  const m = disponibles.find((x) => x.cle === cle) ?? disponibles[0];
  if (!m || lignes.length < 2) return null;

  const points = lignes
    .map((l) => ({ l, v: m.valeur(l) }))
    .filter((p): p is { l: LigneTdb; v: number } => p.v != null)
    .sort((a, b) => b.v - a.v);
  const max = Math.max(0, ...points.map((p) => p.v));
  const min = Math.min(0, ...points.map((p) => p.v));
  const etendue = max - min || 1;
  const zero = (-min / etendue) * 72;                         // % de la piste, 28 % gardes aux etiquettes
  const fmt = (v: number) => (m.pct ? pourcent(v) : m.nombre ? entier(v) : montant(v));

  function filtrer(agence: string) {
    if (!cliquable) return;
    const q = new URLSearchParams(parametres.toString());
    q.set("agence", agence);
    router.push(`?${q.toString()}`);
  }

  return (
    <figure className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <figcaption className="text-sm font-semibold text-pop-encre">Comparaison — {m.libelle}</figcaption>
        <label className="text-xs text-pop-gris">
          Indicateur{" "}
          <select value={m.cle} onChange={(e) => setCle(e.target.value)}
            className="ml-1 rounded-md border border-pop-bord bg-white px-2 py-1 text-xs text-pop-encre">
            {disponibles.map((x) => (
              <option key={x.cle} value={x.cle}>{x.libelle}</option>
            ))}
          </select>
        </label>
      </div>
      <ul className="space-y-1.5">
        {points.map(({ l, v }) => {
          const largeur = (Math.abs(v) / etendue) * 72;
          const gauche = v >= 0 ? zero : zero - largeur;
          const id = `${l.agence}-${l.designation}`;
          const agenceCliquable = cliquable && l.fonction === "AGENCE";
          return (
            <li key={id} className="grid grid-cols-1 items-center gap-1 sm:grid-cols-[11rem_1fr] sm:gap-3">
              <span className="truncate text-[13px] text-pop-encre" title={l.designation}>
                {l.designation}
                {l.statut !== "actif" && <span className="ml-1 text-[11px] text-pop-alerte">({l.statut})</span>}
              </span>
              <button
                type="button"
                disabled={!agenceCliquable}
                onClick={() => filtrer(l.agence)}
                onMouseEnter={() => setSurvol(id)}
                onMouseLeave={() => setSurvol(null)}
                onFocus={() => setSurvol(id)}
                onBlur={() => setSurvol(null)}
                aria-label={`${l.designation} : ${fmt(v)}${agenceCliquable ? " — filtrer sur cette agence" : ""}`}
                className="relative h-6 w-full rounded disabled:cursor-default enabled:cursor-pointer focus-visible:outline-2 focus-visible:outline-pop-cyan"
              >
                {min < 0 && <span className="absolute inset-y-0 w-px bg-pop-gris/60" style={{ left: `${zero}%` }} />}
                <span
                  className="absolute top-1/2 h-3.5 -translate-y-1/2 rounded-[4px] bg-[#1B5E86] transition-opacity"
                  style={{ left: `${gauche}%`, width: `${Math.max(largeur, 0.4)}%`, opacity: survol && survol !== id ? 0.45 : 1 }}
                />
                <span
                  className="chiffres absolute top-1/2 -translate-y-1/2 whitespace-nowrap pl-1.5 text-[12px] text-pop-encre"
                  style={{ left: `${v >= 0 ? zero + largeur : zero}%` }}
                >
                  {fmt(v)}
                </span>
                {survol === id && (
                  <span className="pointer-events-none absolute -top-8 right-0 z-10 rounded-md border border-pop-bord bg-white px-2 py-1 text-[11px] text-pop-encre shadow-md">
                    Encours {montant(l.encours)} · PAR30 {pourcent(l.pct_par30 * 100)} · decaisse {montant(l.decaisse_volume)}
                  </span>
                )}
              </button>
            </li>
          );
        })}
      </ul>
      {cliquable && <p className="text-xs text-pop-gris">Cliquer une agence pour filtrer tout le tableau de bord sur elle.</p>}
    </figure>
  );
}
