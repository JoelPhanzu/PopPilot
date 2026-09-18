"use client";

/**
 * PopPilot — formulaire d'import des fichiers du CBS.
 *
 * Le formulaire est ENTIEREMENT construit a partir du catalogue renvoye par
 * l'API : domaines, extensions acceptees, champs obligatoires et facultatifs.
 * Rien n'est code en dur ici — ajouter un domaine cote moteur le fait
 * apparaitre a l'ecran sans toucher a ce fichier.
 */
import { useActionState, useState } from "react";
import { useFormStatus } from "react-dom";
import {
  AIDES_CHAMP,
  ETAT_INITIAL,
  LIBELLES_CHAMP,
  poids,
  typeDeChamp,
  type DomaineImport,
} from "@/lib/import";
import { importerFichier } from "./actions";

function BoutonEnvoyer({ libelle }: { libelle: string }) {
  const { pending } = useFormStatus();
  return (
    <button
      type="submit"
      disabled={pending}
      className="rounded-lg bg-pop-bleu px-5 py-2.5 text-sm font-medium text-white transition
                 hover:bg-pop-bleu-2 focus:outline-none focus-visible:ring-2
                 focus-visible:ring-pop-cyan disabled:cursor-progress disabled:opacity-60"
    >
      {pending ? "Import en cours…" : libelle}
    </button>
  );
}

function Champ({ nom, obligatoire }: { nom: string; obligatoire: boolean }) {
  const type = typeDeChamp(nom);
  return (
    <label className="block">
      <span className="text-sm font-medium text-pop-encre">
        {LIBELLES_CHAMP[nom] ?? nom}
        {obligatoire ? (
          <span className="ml-1 text-pop-danger" aria-hidden>
            *
          </span>
        ) : (
          <span className="ml-1 text-xs font-normal text-pop-gris">(facultatif)</span>
        )}
      </span>
      <input
        name={nom}
        type={type}
        required={obligatoire}
        placeholder={nom === "devise" ? "USD" : undefined}
        className="mt-1 w-full rounded-lg border border-pop-bord bg-white px-3 py-2 text-sm
                   text-pop-encre focus:border-pop-cyan focus:outline-none
                   focus-visible:ring-2 focus-visible:ring-pop-cyan/40"
      />
      {AIDES_CHAMP[nom] && (
        <span className="mt-1 block text-xs leading-relaxed text-pop-gris">{AIDES_CHAMP[nom]}</span>
      )}
    </label>
  );
}

export function FormulaireImport({
  domaines,
  tailleMaxMo,
}: {
  domaines: DomaineImport[];
  tailleMaxMo: number;
}) {
  const [etat, action] = useActionState(importerFichier, ETAT_INITIAL);
  const [cle, setCle] = useState(domaines[0]?.cle ?? "");
  const domaine = domaines.find((d) => d.cle === cle) ?? domaines[0];

  if (!domaine) {
    return <p className="text-sm text-pop-gris">L&apos;API n&apos;expose aucun domaine d&apos;import.</p>;
  }

  return (
    <form action={action} className="space-y-5">
      <label className="block">
        <span className="text-sm font-medium text-pop-encre">Nature du fichier</span>
        <select
          name="domaine"
          value={cle}
          onChange={(e) => setCle(e.target.value)}
          className="mt-1 w-full rounded-lg border border-pop-bord bg-white px-3 py-2 text-sm
                     text-pop-encre focus:border-pop-cyan focus:outline-none
                     focus-visible:ring-2 focus-visible:ring-pop-cyan/40"
        >
          {domaines.map((d) => (
            <option key={d.cle} value={d.cle}>
              {d.libelle}
            </option>
          ))}
        </select>
        <span className="mt-1 block text-xs leading-relaxed text-pop-gris">{domaine.aide}</span>
      </label>

      {/* `key` : changer de domaine remet le champ fichier a zero, sinon un .csv
          choisi pour l'epargne resterait selectionne pour le credit, qui le refuse. */}
      <label className="block" key={domaine.cle}>
        <span className="text-sm font-medium text-pop-encre">
          Fichier <span className="text-pop-danger" aria-hidden>*</span>
        </span>
        <input
          name="fichier"
          type="file"
          required
          accept={domaine.extensions.join(",")}
          className="mt-1 w-full rounded-lg border border-dashed border-pop-bord bg-white px-3 py-2
                     text-sm text-pop-encre file:mr-3 file:rounded-md file:border-0
                     file:bg-pop-fond file:px-3 file:py-1.5 file:text-sm file:text-pop-bleu"
        />
        <span className="mt-1 block text-xs text-pop-gris">
          {domaine.extensions.join(", ")} &middot; {tailleMaxMo} Mo maximum
        </span>
      </label>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {domaine.requis.map((c) => (
          <Champ key={c} nom={c} obligatoire />
        ))}
        {domaine.optionnels.map((c) => (
          <Champ key={c} nom={c} obligatoire={false} />
        ))}
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <BoutonEnvoyer libelle={`Importer — ${domaine.libelle}`} />
        <span className="text-xs leading-relaxed text-pop-gris">
          Ré-importer le même arrêté REMPLACE le chargement précédent&nbsp;: jamais de doublon.
        </span>
      </div>

      {/* Un import qui ne charge AUCUNE ligne n'est pas un succes : le fichier a bien
          ete lu, mais il n'a rien donne — et la purge du chargement precedent, elle,
          a eu lieu. L'annoncer en vert laisserait croire que la base est alimentee. */}
      {etat.etat === "succes" && (
        <div
          role="status"
          className={
            etat.resultat.lignes_chargees === 0
              ? "rounded-xl border border-pop-alerte/30 bg-pop-alerte/5 px-4 py-3 text-sm text-pop-alerte"
              : "rounded-xl border border-pop-ok/30 bg-pop-ok/5 px-4 py-3 text-sm text-pop-ok"
          }
        >
          <p className="font-semibold">
            {etat.resultat.lignes_chargees === 0
              ? `Aucune ligne chargee — ${etat.resultat.libelle}. Verifier qu'il s'agit du bon fichier.`
              : `${etat.resultat.lignes_chargees.toLocaleString("fr-FR")} ligne(s) chargee(s) — ${etat.resultat.libelle}.`}
          </p>
          <p className="mt-1 text-[13px] leading-relaxed">
            {etat.resultat.fichier} ({poids(etat.resultat.octets)}) &middot; base&nbsp;:{" "}
            {etat.resultat.base}
            {typeof etat.resultat.resultat.purges === "number" &&
              etat.resultat.resultat.purges > 0 && (
                <>
                  {" "}
                  &middot; {Number(etat.resultat.resultat.purges).toLocaleString("fr-FR")} ligne(s)
                  du chargement precedent remplacee(s)
                </>
              )}
            {typeof etat.resultat.resultat.rejetees === "number" &&
              etat.resultat.resultat.rejetees > 0 && (
                <>
                  {" "}
                  &middot;{" "}
                  <strong>
                    {Number(etat.resultat.resultat.rejetees).toLocaleString("fr-FR")} ligne(s)
                    rejetee(s)
                  </strong>
                </>
              )}
          </p>
        </div>
      )}

      {etat.etat === "echec" && (
        <div
          role="alert"
          className="rounded-xl border border-pop-danger/30 bg-pop-danger/5 px-4 py-3 text-sm text-pop-danger"
        >
          <p className="font-semibold">
            Import refuse{etat.statut === null ? "" : ` (${etat.statut})`} — rien n&apos;a ete
            ecrit.
          </p>
          <p className="mt-1 text-[13px] leading-relaxed">{etat.message}</p>
        </div>
      )}
    </form>
  );
}
