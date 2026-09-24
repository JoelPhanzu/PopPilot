"use client";

/**
 * PopPilot — les DEUX controles de temps du tableau de bord (doctrine flux/stock).
 *
 *  - Date de VALORISATION (stocks : encours, PAR, provisions, clients) ;
 *  - PERIODE DE FLUX [debut ; fin] (decaissements, P15), independante.
 * Le cout du risque et les migrations comparent l'arrete a l'arrete M-1.
 * Tout vit dans l'URL : l'ecran est partageable et rejouable a l'identique.
 */
import { useRouter, useSearchParams } from "next/navigation";
import { useState, useTransition } from "react";
import { dateArreteValide } from "@/lib/format";

const champ =
  "chiffres mt-1 rounded-lg border border-pop-bord bg-white px-3 py-1.5 text-sm text-pop-encre outline-none focus:border-pop-cyan focus:ring-2 focus:ring-pop-cyan/30";

export function SelecteurPeriodeCredit({
  arrete,
  debut,
  fin,
  precedent,
}: {
  arrete: string;
  debut: string;
  fin: string;
  precedent: string | null;
}) {
  const router = useRouter();
  const parametres = useSearchParams();
  const [v, setV] = useState({ arrete, debut, fin });
  const [enCours, demarrer] = useTransition();
  const valide =
    dateArreteValide(v.arrete) && dateArreteValide(v.debut) && dateArreteValide(v.fin) && v.debut <= v.fin;

  function aller(c: { arrete: string; debut: string; fin: string }) {
    const q = new URLSearchParams(parametres.toString());
    q.set("arrete", c.arrete);
    q.set("debut", c.debut);
    q.set("fin", c.fin);
    demarrer(() => router.push(`?${q.toString()}`));
  }

  const [a, m] = v.arrete.split("-");
  const finMois = new Date(Date.UTC(Number(a), Number(m), 0)).toISOString().slice(0, 10);
  const raccourcis = [
    { libelle: "Mois de l'arrete", debut: `${a}-${m}-01`, fin: v.arrete },
    { libelle: "1re quinzaine", debut: `${a}-${m}-01`, fin: `${a}-${m}-15` },
    { libelle: "2e quinzaine", debut: `${a}-${m}-16`, fin: finMois < v.arrete ? finMois : v.arrete },
    { libelle: "Depuis janvier", debut: `${a}-01-01`, fin: v.arrete },
  ];

  return (
    <section
      aria-label="Dates du tableau de bord"
      className="rounded-xl border border-pop-bord bg-pop-carte px-4 py-3 shadow-sm"
    >
      <div className="flex flex-wrap items-end gap-4">
        <div>
          <label htmlFor="tdb-arrete" className="block text-[12px] font-medium text-pop-gris">
            Date de valorisation (stocks)
          </label>
          <input id="tdb-arrete" type="date" value={v.arrete} className={champ}
            onChange={(e) => setV({ ...v, arrete: e.target.value })} />
        </div>
        <div className="flex items-end gap-2 border-l border-pop-bord pl-4">
          <div>
            <label htmlFor="tdb-debut" className="block text-[12px] font-medium text-pop-gris">
              Flux : du
            </label>
            <input id="tdb-debut" type="date" value={v.debut} className={champ}
              onChange={(e) => setV({ ...v, debut: e.target.value })} />
          </div>
          <div>
            <label htmlFor="tdb-fin" className="block text-[12px] font-medium text-pop-gris">
              au
            </label>
            <input id="tdb-fin" type="date" value={v.fin} className={champ}
              onChange={(e) => setV({ ...v, fin: e.target.value })} />
          </div>
        </div>
        <button
          type="button"
          onClick={() => aller(v)}
          disabled={!valide || enCours}
          className="rounded-lg bg-pop-bleu px-4 py-2 text-sm font-medium text-white hover:bg-pop-bleu-2 disabled:opacity-45"
        >
          {enCours ? "Calcul…" : "Afficher"}
        </button>
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-2 text-xs">
        <span className="text-pop-gris">Periode de flux :</span>
        {raccourcis.map((r) => (
          <button
            key={r.libelle}
            type="button"
            onClick={() => aller({ arrete: v.arrete, debut: r.debut, fin: r.fin })}
            className="rounded-full border border-pop-bord px-2.5 py-0.5 text-pop-bleu-2 hover:border-pop-cyan"
          >
            {r.libelle}
          </button>
        ))}
        <span className="ml-auto text-pop-gris">
          Comparaison M-1 : {precedent ?? "aucun arrete anterieur charge"}
        </span>
      </div>
      {!valide && <p className="mt-1 text-xs text-pop-danger">Dates invalides ou periode inversee.</p>}
    </section>
  );
}
