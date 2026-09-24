/**
 * PopPilot — evolution d'un indicateur (serie temporelle, une seule serie).
 *
 * Choix (methode dataviz) : UNE serie → une couleur (#1B5E86, bleu de charte
 * deja retenu pour le graphique du PAR), pas de legende : le titre nomme la
 * courbe. Ligne 2 px, points de 8 px focusables au clavier avec infobulle
 * native (date, valeur, source), grille horizontale discrete, un seul axe.
 * Axe des dates PROPORTIONNEL au temps : des arretes irreguliers (dec. 2025,
 * puis mai, juin…) ne sont pas equidistants. Le tableau qui suit est la vue
 * texte equivalente.
 */
import { montant, montantCompact } from "@/lib/format";
import type { PointSerie } from "@/lib/archives";

const L = 720;
const H = 260;
const M = { haut: 16, droite: 16, bas: 28, gauche: 64 };

function graduations(min: number, max: number): number[] {
  const etendue = max - min || Math.abs(max) || 1;
  const brut = etendue / 4;
  const puissance = 10 ** Math.floor(Math.log10(brut));
  const pas = [1, 2, 2.5, 5, 10].map((m) => m * puissance).find((p) => p >= brut) ?? puissance * 10;
  const debut = Math.floor(min / pas) * pas;
  const fin = Math.ceil(max / pas) * pas;
  return Array.from({ length: Math.round((fin - debut) / pas) + 1 }, (_, i) => debut + i * pas);
}

export function CourbeSerie({ titre, points, unite }: { titre: string; points: PointSerie[]; unite: string | null }) {
  if (points.length === 0) return <p className="text-sm text-pop-gris">Aucun point pour cette serie.</p>;

  const temps = points.map((p) => new Date(p.date).getTime());
  const valeurs = points.map((p) => p.valeur);
  const zero = unite !== "%" && Math.min(...valeurs) >= 0;
  const ticks = graduations(zero ? 0 : Math.min(...valeurs), Math.max(...valeurs));
  const [bas, haut] = [ticks[0], ticks[ticks.length - 1]];
  const t0 = Math.min(...temps);
  const t1 = Math.max(...temps);
  const x = (t: number) => M.gauche + (t1 === t0 ? 0.5 : (t - t0) / (t1 - t0)) * (L - M.gauche - M.droite);
  const y = (v: number) => M.haut + (1 - (v - bas) / (haut - bas || 1)) * (H - M.haut - M.bas);
  const chemin = points.map((p, i) => `${i ? "L" : "M"}${x(temps[i]).toFixed(1)},${y(p.valeur).toFixed(1)}`).join(" ");
  const format = (v: number) => (unite === "%" ? `${v.toFixed(2)} %` : unite === "nombre" ? v.toLocaleString("fr-FR") : montant(v));

  return (
    <figure className="space-y-2">
      <figcaption className="text-sm font-semibold text-pop-encre">
        {titre} {unite && <span className="font-normal text-pop-gris">({unite})</span>}
      </figcaption>
      <svg viewBox={`0 0 ${L} ${H}`} className="w-full" role="img" aria-label={`Evolution : ${titre}`}>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={M.gauche} x2={L - M.droite} y1={y(t)} y2={y(t)} stroke="#E2E8F0" strokeWidth={1} />
            <text x={M.gauche - 8} y={y(t) + 4} textAnchor="end" fontSize={11} fill="#58595B">
              {unite === "%" ? `${t} %` : montantCompact(t)}
            </text>
          </g>
        ))}
        {[points[0], points[points.length - 1]].map((p, i) => (
          <text
            key={`${p.date}-${i}`}
            x={x(new Date(p.date).getTime())}
            y={H - 8}
            textAnchor={i === 0 ? "start" : "end"}
            fontSize={11}
            fill="#58595B"
          >
            {p.date}
          </text>
        ))}
        <path d={chemin} fill="none" stroke="#1B5E86" strokeWidth={2} strokeLinejoin="round" />
        {points.map((p, i) => (
          <circle
            key={p.date}
            cx={x(temps[i])}
            cy={y(p.valeur)}
            r={4}
            fill={p.source === "calcul_poppilot" ? "#1B5E86" : "#FFFFFF"}
            stroke="#1B5E86"
            strokeWidth={2}
            tabIndex={0}
            className="outline-none focus:stroke-[3px]"
          >
            <title>{`${p.date} : ${format(p.valeur)} — ${p.source === "calcul_poppilot" ? "calcul PopPilot" : "historique importe"}`}</title>
          </circle>
        ))}
      </svg>
      <p className="text-xs text-pop-gris">
        Point plein : calcule par les moteurs PopPilot · point creux : historique importe.
      </p>
    </figure>
  );
}
