/**
 * PopPilot — migrations du portefeuille (arrete M-1 → arrete), engine/migrations.
 *
 * Barres verticales, une seule serie (#1B5E86) : « Entree en PAR » puis les
 * tranches de migration. ⚠️ Libelles du Dashboard reproduits fidelement : une
 * « migration vers 31-60 » regroupe les prets PARTIS de la tranche precedente
 * (classement par tranche de DEPART, code M-1). Valeur ecrite sur chaque barre ;
 * infobulle au survol et au focus (<title>).
 */
import { entier, montant, montantCompact } from "@/lib/format";

export function GraphiqueMigrations({
  entreeNb,
  entreeMontant,
  migrations,
  coutDuRisque,
}: {
  entreeNb: number;
  entreeMontant: number;
  migrations: Record<string, number>;
  coutDuRisque: number;
}) {
  const barres = [
    { libelle: "Entree en PAR", valeur: entreeMontant, note: `${entier(entreeNb)} credits passes de sain a >= 1 jour` },
    ...Object.entries(migrations).map(([t, v]) => ({ libelle: `Vers ${t}`, valeur: v, note: "classe par tranche de depart (M-1)" })),
  ];
  const max = Math.max(1, ...barres.map((b) => b.valeur));
  const L = 560;
  const H = 200;
  const bas = 34;
  const largeur = L / barres.length;

  return (
    <figure className="space-y-2">
      <figcaption className="flex flex-wrap items-baseline justify-between gap-2 text-sm font-semibold text-pop-encre">
        <span>Migrations du portefeuille (M-1 → arrete)</span>
        <span className="text-xs font-normal text-pop-gris">
          Cout du risque : <span className="chiffres font-semibold text-pop-encre">{montant(coutDuRisque)}</span>
        </span>
      </figcaption>
      <svg viewBox={`0 0 ${L} ${H}`} className="w-full" role="img" aria-label="Migrations par tranche">
        <line x1={0} x2={L} y1={H - bas} y2={H - bas} stroke="#E2E8F0" />
        {barres.map((b, i) => {
          const h = ((H - bas - 18) * b.valeur) / max;
          const x = i * largeur + largeur * 0.25;
          return (
            <g key={b.libelle} tabIndex={0} className="outline-none">
              <title>{`${b.libelle} : ${montant(b.valeur)} — ${b.note}`}</title>
              <rect x={x} y={H - bas - h} width={largeur * 0.5} height={Math.max(h, 0)} rx={4} fill="#1B5E86" />
              <text x={x + largeur * 0.25} y={H - bas - h - 5} textAnchor="middle" fontSize={11} fill="#1F2A33">
                {montantCompact(b.valeur)}
              </text>
              <text x={x + largeur * 0.25} y={H - 14} textAnchor="middle" fontSize={11} fill="#58595B">
                {b.libelle}
              </text>
            </g>
          );
        })}
      </svg>
    </figure>
  );
}
