"use client";

/**
 * PopPilot — decaissements A DATE, jour par jour sur la periode de flux.
 *
 * Deux vues commutables plutot qu'un double axe (interdit : deux echelles) :
 *  - « Par jour » : barres fines, une par jour ;
 *  - « Cumul »    : courbe du cumul + ligne de reference « objectif » (meme unite).
 * Mesure au choix : volume (USD) ou nombre. Une seule serie → une couleur
 * (#1B5E86) ; l'objectif est un repere gris en tirets, libelle en clair.
 * Survol / clavier (fleches) : detail du jour dans une infobulle.
 */
import { useState } from "react";
import { entier, montant, montantCompact } from "@/lib/format";
import type { JourDecaissement } from "@/lib/credit-tdb";

const L = 760;
const H = 240;
const M = { haut: 14, droite: 12, bas: 26, gauche: 60 };

function graduations(max: number): number[] {
  if (!(max > 0)) return [0];
  const brut = max / 4;
  const p = 10 ** Math.floor(Math.log10(brut));
  const pas = [1, 2, 2.5, 5, 10].map((m) => m * p).find((x) => x >= brut) ?? p * 10;
  return Array.from({ length: Math.ceil(max / pas) + 1 }, (_, i) => i * pas);
}

export function GraphiqueDecaissementsJour({
  jours,
  objectifVolume,
  objectifNombre,
}: {
  jours: JourDecaissement[];
  objectifVolume: number | null;
  objectifNombre: number | null;
}) {
  const [vue, setVue] = useState<"jour" | "cumul">("cumul");
  const [mesure, setMesure] = useState<"volume" | "nombre">("volume");
  const [survol, setSurvol] = useState<number | null>(null);
  if (jours.length === 0) return null;

  const val = (j: JourDecaissement) =>
    vue === "jour" ? (mesure === "volume" ? j.volume : j.nombre) : mesure === "volume" ? j.cumul_volume : j.cumul_nombre;
  const objectif = vue === "cumul" ? (mesure === "volume" ? objectifVolume : objectifNombre) : null;
  const ticks = graduations(Math.max(...jours.map(val), objectif ?? 0));
  const haut = ticks[ticks.length - 1] || 1;
  const largeurPiste = L - M.gauche - M.droite;
  const pas = largeurPiste / jours.length;
  const x = (i: number) => M.gauche + pas * (i + 0.5);
  const y = (v: number) => M.haut + (1 - v / haut) * (H - M.haut - M.bas);
  const fmt = (v: number) => (mesure === "volume" ? montant(v) : entier(v));
  const j = survol === null ? null : jours[survol];
  const bouton = (actif: boolean) =>
    `rounded-md px-2.5 py-1 text-xs ${actif ? "bg-pop-bleu text-white" : "text-pop-gris hover:text-pop-encre"}`;

  return (
    <figure className="space-y-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <figcaption className="text-sm font-semibold text-pop-encre">
          Decaissements a date — {mesure === "volume" ? "volume (USD)" : "nombre"}
          {vue === "cumul" ? ", cumul sur la periode" : ", par jour"}
        </figcaption>
        <div className="flex gap-3">
          <div className="flex rounded-lg border border-pop-bord p-0.5" role="group" aria-label="Vue">
            <button type="button" className={bouton(vue === "cumul")} onClick={() => setVue("cumul")}>Cumul</button>
            <button type="button" className={bouton(vue === "jour")} onClick={() => setVue("jour")}>Par jour</button>
          </div>
          <div className="flex rounded-lg border border-pop-bord p-0.5" role="group" aria-label="Mesure">
            <button type="button" className={bouton(mesure === "volume")} onClick={() => setMesure("volume")}>Volume</button>
            <button type="button" className={bouton(mesure === "nombre")} onClick={() => setMesure("nombre")}>Nombre</button>
          </div>
        </div>
      </div>
      <div className="relative">
        <svg
          viewBox={`0 0 ${L} ${H}`}
          className="w-full"
          role="img"
          aria-label="Decaissements jour par jour"
          tabIndex={0}
          onKeyDown={(e) => {
            if (e.key === "ArrowRight") setSurvol((s) => Math.min(jours.length - 1, (s ?? -1) + 1));
            if (e.key === "ArrowLeft") setSurvol((s) => Math.max(0, (s ?? jours.length) - 1));
          }}
          onMouseLeave={() => setSurvol(null)}
          onBlur={() => setSurvol(null)}
        >
          {ticks.map((t) => (
            <g key={t}>
              <line x1={M.gauche} x2={L - M.droite} y1={y(t)} y2={y(t)} stroke="#E2E8F0" />
              <text x={M.gauche - 6} y={y(t) + 4} textAnchor="end" fontSize={11} fill="#58595B">
                {mesure === "volume" ? montantCompact(t) : entier(t)}
              </text>
            </g>
          ))}
          {[0, jours.length - 1].map((i) => (
            <text key={i} x={x(i)} y={H - 6} textAnchor={i === 0 ? "start" : "end"} fontSize={11} fill="#58595B">
              {jours[i].date.slice(8, 10)}/{jours[i].date.slice(5, 7)}
            </text>
          ))}
          {vue === "jour" ? (
            jours.map((d, i) => {
              const h = y(0) - y(val(d));
              return h > 0 ? (
                <rect key={d.date} x={x(i) - Math.min(6, pas * 0.35)} y={y(val(d))}
                  width={Math.min(12, pas * 0.7)} height={h} rx={2}
                  fill="#1B5E86" opacity={survol === null || survol === i ? 1 : 0.45} />
              ) : null;
            })
          ) : (
            <path
              d={jours.map((d, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(val(d)).toFixed(1)}`).join(" ")}
              fill="none" stroke="#1B5E86" strokeWidth={2} strokeLinejoin="round"
            />
          )}
          {objectif != null && objectif > 0 && (
            <g>
              <line x1={M.gauche} x2={L - M.droite} y1={y(objectif)} y2={y(objectif)}
                stroke="#58595B" strokeDasharray="5 4" />
              <text x={L - M.droite} y={y(objectif) - 5} textAnchor="end" fontSize={11} fill="#58595B">
                Objectif du mois {fmt(objectif)}
              </text>
            </g>
          )}
          {survol !== null && (
            <g>
              <line x1={x(survol)} x2={x(survol)} y1={M.haut} y2={H - M.bas} stroke="#58595B" strokeWidth={1} />
              {vue === "cumul" && <circle cx={x(survol)} cy={y(val(jours[survol]))} r={4} fill="#1B5E86" stroke="#fff" strokeWidth={2} />}
            </g>
          )}
          {jours.map((d, i) => (
            <rect key={`z-${d.date}`} x={M.gauche + pas * i} y={M.haut} width={pas} height={H - M.haut - M.bas}
              fill="transparent" onMouseEnter={() => setSurvol(i)} />
          ))}
        </svg>
        {j && (
          <div
            role="status"
            className="pointer-events-none absolute top-2 rounded-lg border border-pop-bord bg-white px-3 py-2 text-xs shadow-md"
            style={{ left: `${Math.min(75, (x(survol!) / L) * 100)}%` }}
          >
            <p className="font-semibold text-pop-encre">{j.date.split("-").reverse().join("/")}</p>
            <p className="chiffres text-pop-gris">Jour : {entier(j.nombre)} credit(s) · {montant(j.volume)}</p>
            <p className="chiffres text-pop-gris">Cumul : {entier(j.cumul_nombre)} · {montant(j.cumul_volume)}</p>
          </div>
        )}
      </div>
    </figure>
  );
}
