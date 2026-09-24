"use client";

/**
 * PopPilot — barre de filtres du tableau de bord credit (chantiers 1-2).
 *
 * Meme doctrine que SelecteurArrete : UNE barre au-dessus de tout ce qu'elle
 * gouverne, et l'etat vit dans l'URL (?agence=…&produits=A&produits=B…) —
 * l'ecran filtre est partageable et rejouable a l'identique.
 *
 * Aucun calcul ici : les menus viennent de GET /credit/filtres/valeurs (deja
 * limites au perimetre du role), et les chiffres de GET /credit/filtre. Un role
 * AGENCE n'a pas de menu agence : l'API l'y ramene de toute facon (403 sinon).
 */
import { useRouter, useSearchParams } from "next/navigation";
import { useState, useTransition } from "react";
import type { FiltresCredit, ValeursFiltres } from "@/lib/credit";

const LIBELLES_DUREE: Record<string, string> = {
  court: "Court terme (≤ 12 mois + LISANGA)",
  moyen: "Moyen terme (13–24 mois)",
  long: "Long terme (> 24 mois)",
};

const LIBELLES_SEXE: Record<string, string> = { F: "Femme", H: "Homme" };

const champ =
  "mt-1 w-full rounded-lg border border-pop-bord bg-white px-2.5 py-1.5 text-sm text-pop-encre " +
  "outline-none focus:border-pop-cyan focus:ring-2 focus:ring-pop-cyan/30";
const etiquette = "block text-[12px] font-medium text-pop-gris";

function Choix({
  id,
  libelle,
  valeur,
  options,
  libelles,
  onChange,
}: {
  id: string;
  libelle: string;
  valeur: string;
  options: string[];
  libelles?: Record<string, string>;
  onChange: (v: string) => void;
}) {
  return (
    <div className="min-w-0">
      <label htmlFor={id} className={etiquette}>
        {libelle}
      </label>
      <select id={id} value={valeur} onChange={(e) => onChange(e.target.value)} className={champ}>
        <option value="">Tous</option>
        {options.map((o) => (
          <option key={o} value={o}>
            {libelles?.[o] ?? o}
          </option>
        ))}
      </select>
    </div>
  );
}

export function BarreFiltresCredit({
  valeurs,
  filtres,
  agenceFixe,
}: {
  valeurs: ValeursFiltres;
  filtres: FiltresCredit;
  /** Role AGENCE : pas de choix d'agence, le perimetre est impose. */
  agenceFixe: string | null;
}) {
  const router = useRouter();
  const parametres = useSearchParams();
  const [enCours, demarrer] = useTransition();
  const [f, setF] = useState<FiltresCredit>(filtres);

  const maj = (k: keyof FiltresCredit) => (v: string) => setF((x) => ({ ...x, [k]: v || undefined }));

  function basculerProduit(p: string) {
    setF((x) => {
      const actuels = new Set(x.produits ?? []);
      if (actuels.has(p)) actuels.delete(p);
      else actuels.add(p);
      return { ...x, produits: actuels.size ? [...actuels] : undefined };
    });
  }

  function naviguer(cible: FiltresCredit) {
    // On repart de l'URL pour garder ?arrete=… ; les axes sont reecrits en entier.
    const q = new URLSearchParams();
    // Les controles de temps et le niveau ne sont pas des filtres : on les garde.
    for (const garde of ["arrete", "debut", "fin", "niveau"]) {
      const valeur = parametres.get(garde);
      if (valeur) q.set(garde, valeur);
    }
    for (const [k, v] of Object.entries(cible)) {
      if (Array.isArray(v)) v.forEach((p) => q.append(k, p));
      else if (v) q.set(k, v);
    }
    demarrer(() => router.push(`?${q.toString()}`));
  }

  const nbProduits = f.produits?.length ?? 0;

  return (
    <section
      aria-label="Filtres du portefeuille"
      className="rounded-xl border border-pop-bord bg-pop-carte px-4 py-3 shadow-sm"
    >
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {agenceFixe === null && (
          <Choix
            id="f-agence"
            libelle="Agence"
            valeur={f.agence ?? ""}
            options={valeurs.agences}
            onChange={maj("agence")}
          />
        )}
        <Choix
          id="f-superviseur"
          libelle="Superviseur"
          valeur={f.superviseur ?? ""}
          options={valeurs.superviseurs}
          onChange={maj("superviseur")}
        />
        <Choix
          id="f-agent"
          libelle="Agent de credit"
          valeur={f.agent ?? ""}
          options={valeurs.agents}
          onChange={maj("agent")}
        />
        <Choix
          id="f-sexe"
          libelle="Sexe"
          valeur={f.sexe ?? ""}
          options={valeurs.sexes}
          libelles={LIBELLES_SEXE}
          onChange={maj("sexe")}
        />
        <Choix
          id="f-duree"
          libelle="Duree"
          valeur={f.duree ?? ""}
          options={valeurs.durees}
          libelles={LIBELLES_DUREE}
          onChange={maj("duree")}
        />
        <div className="min-w-0">
          <label htmlFor="f-client" className={etiquette}>
            N° client
          </label>
          <input
            id="f-client"
            value={f.client ?? ""}
            onChange={(e) => maj("client")(e.target.value.trim())}
            onKeyDown={(e) => {
              if (e.key === "Enter") naviguer(f);
            }}
            placeholder="ex. 100245"
            className={`chiffres ${champ}`}
          />
        </div>
        <details className="relative min-w-0 sm:col-span-2">
          <summary className={`${etiquette} cursor-pointer select-none`}>
            Produits{" "}
            <span className="text-pop-encre">
              {nbProduits ? `(${nbProduits} selectionne${nbProduits > 1 ? "s" : ""})` : "(tous)"}
            </span>
          </summary>
          <fieldset className="mt-1 grid max-h-48 grid-cols-1 gap-1 overflow-y-auto rounded-lg border border-pop-bord bg-white p-2 sm:grid-cols-2">
            <legend className="sr-only">Produits de credit</legend>
            {valeurs.produits.map((p) => (
              <label key={p} className="flex items-center gap-2 text-[13px] text-pop-encre">
                <input
                  type="checkbox"
                  checked={f.produits?.includes(p) ?? false}
                  onChange={() => basculerProduit(p)}
                  className="accent-pop-bleu"
                />
                <span className="truncate">{p}</span>
              </label>
            ))}
          </fieldset>
        </details>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={() => naviguer(f)}
          disabled={enCours}
          className="rounded-lg bg-pop-bleu px-4 py-2 text-sm font-medium text-white transition hover:bg-pop-bleu-2
                     focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-pop-cyan
                     disabled:cursor-not-allowed disabled:opacity-45"
        >
          {enCours ? "Calcul…" : "Appliquer les filtres"}
        </button>
        <button
          type="button"
          onClick={() => {
            setF({});
            naviguer({});
          }}
          disabled={enCours}
          className="lien-pop text-sm font-medium disabled:opacity-45"
        >
          Reinitialiser
        </button>
        {agenceFixe !== null && (
          <p className="text-xs text-pop-gris">Perimetre impose&nbsp;: {agenceFixe}</p>
        )}
      </div>
    </section>
  );
}
