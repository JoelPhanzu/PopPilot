"use client";

/**
 * PopPilot — generation d'un rapport reglementaire.
 *
 * Le formulaire est construit a partir du CATALOGUE de l'API : fichiers,
 * extensions, champs et textes d'aide viennent du moteur. Rien n'est code ici.
 *
 * L'envoi se fait en JavaScript plutot que par une soumission de formulaire
 * ordinaire, pour une raison precise : une soumission classique ferait NAVIGUER
 * le navigateur vers la reponse. En cas d'echec, l'utilisateur atterrirait sur
 * une page blanche portant « Balance CDF absente » et aurait perdu sa saisie —
 * gabarit compris, qu'il faudrait re-selectionner. Ici, l'echec s'affiche SOUS
 * le formulaire, qui reste rempli.
 *
 * Le document produit n'est jamais ouvert dans un onglet : il est enregistre.
 * Un .xls de la BCC ouvert dans un navigateur ne veut rien dire.
 */
import { useRef, useState } from "react";
import {
  ETAT_RAPPORT_INITIAL,
  accepte,
  pasDeSaisie,
  typeHtml,
  type EtatRapport,
  type Rapport,
} from "@/lib/rapports";

/** Nom de fichier propose par l'API (en-tete Content-Disposition). */
function nomPropose(entete: string | null, defaut: string): string {
  if (!entete) return defaut;
  // `filename*` (RFC 5987) porte les accents et prime sur `filename`.
  const etoile = /filename\*=UTF-8''([^;]+)/i.exec(entete);
  if (etoile) {
    try {
      return decodeURIComponent(etoile[1]);
    } catch {
      /* valeur mal encodee : on retombe sur `filename` */
    }
  }
  const simple = /filename="?([^";]+)"?/i.exec(entete);
  return simple ? simple[1] : defaut;
}

export function FormulaireRapport({ rapport }: { rapport: Rapport }) {
  const [etat, setEtat] = useState<EtatRapport>(ETAT_RAPPORT_INITIAL);
  const [enCours, setEnCours] = useState(false);
  const [produit, setProduit] = useState<string | null>(null);
  const formulaire = useRef<HTMLFormElement>(null);

  async function envoyer(evenement: React.FormEvent<HTMLFormElement>) {
    evenement.preventDefault();
    setEtat(ETAT_RAPPORT_INITIAL);
    setProduit(null);
    setEnCours(true);

    try {
      const corps = new FormData(evenement.currentTarget);
      const reponse = await fetch(`/api/rapports/${rapport.cle}`, {
        method: "POST",
        body: corps,
      });

      if (!reponse.ok) {
        setEtat({
          etat: "echec",
          statut: reponse.status,
          message: (await reponse.text()) || `Echec (HTTP ${reponse.status}).`,
        });
        return;
      }

      const nom = nomPropose(
        reponse.headers.get("content-disposition"),
        `${rapport.cle}${rapport.extension_sortie}`,
      );
      const blob = await reponse.blob();
      const lien = document.createElement("a");
      lien.href = URL.createObjectURL(blob);
      lien.download = nom;
      document.body.appendChild(lien);
      lien.click();
      lien.remove();
      // L'URL d'objet retient le blob en memoire tant qu'elle existe : un
      // rapport de plusieurs Mo y resterait jusqu'au rechargement de la page.
      URL.revokeObjectURL(lien.href);
      setProduit(nom);
    } catch (e) {
      setEtat({
        etat: "echec",
        statut: null,
        message: `Envoi interrompu : ${e instanceof Error ? e.message : String(e)}`,
      });
    } finally {
      setEnCours(false);
    }
  }

  const champInput =
    "mt-1 w-full rounded-lg border border-pop-bord bg-white px-3 py-2 text-sm text-pop-encre " +
    "focus:border-pop-cyan focus:outline-none focus-visible:ring-2 focus-visible:ring-pop-cyan/40";

  return (
    <section className="overflow-hidden rounded-xl border border-pop-bord bg-pop-carte shadow-sm">
      <header className="border-b border-pop-bord px-5 py-4">
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="text-base font-semibold text-pop-encre">{rapport.libelle}</h2>
          {rapport.remplit_gabarit ? (
            <span className="rounded-full bg-pop-ok/10 px-2.5 py-0.5 text-[11px] font-medium text-pop-ok">
              remplit le gabarit officiel
            </span>
          ) : (
            <span className="rounded-full bg-pop-alerte/10 px-2.5 py-0.5 text-[11px] font-medium text-pop-alerte">
              classeur de resultats — pas la declaration
            </span>
          )}
        </div>
        <p className="mt-1 text-[13px] text-pop-gris">{rapport.description}</p>
        <p className="mt-1.5 text-[12px] leading-relaxed text-pop-gris">{rapport.aide}</p>
      </header>

      <form ref={formulaire} onSubmit={envoyer} className="space-y-4 px-5 py-4">
        {rapport.fichiers.map((f) => (
          <label key={f.nom} className="block">
            <span className="text-sm font-medium text-pop-encre">
              {f.libelle}
              {f.obligatoire ? (
                <span className="ml-1 text-pop-danger" aria-hidden>
                  *
                </span>
              ) : (
                <span className="ml-1 text-xs font-normal text-pop-gris">(facultatif)</span>
              )}
            </span>
            <input
              type="file"
              name={f.nom}
              required={f.obligatoire}
              accept={accepte(f)}
              className={`${champInput} file:mr-3 file:rounded file:border-0 file:bg-pop-fond
                          file:px-3 file:py-1 file:text-[13px] file:text-pop-bleu-2`}
            />
            {f.aide && (
              <span className="mt-1 block text-[11px] leading-relaxed text-pop-gris">
                {f.aide}
              </span>
            )}
          </label>
        ))}

        {rapport.champs.length > 0 && (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {rapport.champs.map((c) => (
              <label key={c.nom} className="block">
                <span className="text-sm font-medium text-pop-encre">
                  {c.libelle}
                  {c.obligatoire ? (
                    <span className="ml-1 text-pop-danger" aria-hidden>
                      *
                    </span>
                  ) : (
                    <span className="ml-1 text-xs font-normal text-pop-gris">
                      (facultatif)
                    </span>
                  )}
                </span>
                <input
                  type={typeHtml(c.type)}
                  step={pasDeSaisie(c.type)}
                  name={c.nom}
                  required={c.obligatoire}
                  className={`${c.type === "texte" ? "" : "chiffres "}${champInput}`}
                />
                {c.aide && (
                  <span className="mt-1 block text-[11px] leading-relaxed text-pop-gris">
                    {c.aide}
                  </span>
                )}
              </label>
            ))}
          </div>
        )}

        <div className="flex flex-wrap items-center gap-3">
          <button
            type="submit"
            disabled={enCours}
            className="rounded-lg bg-pop-bleu px-5 py-2.5 text-sm font-medium text-white transition
                       hover:bg-pop-bleu-2 focus-visible:outline-2 focus-visible:outline-offset-2
                       focus-visible:outline-pop-cyan disabled:cursor-progress disabled:opacity-60"
          >
            {enCours ? "Generation en cours…" : "Generer et telecharger"}
          </button>
          {enCours && (
            <span className="text-[12px] text-pop-gris">
              Les moteurs calculent sur toute la periode&nbsp;: cela peut prendre une minute.
            </span>
          )}
        </div>

        {produit && (
          <p role="status" className="rounded-lg bg-pop-ok/10 px-3 py-2 text-[13px] text-pop-ok">
            Document produit et telecharge&nbsp;: <strong>{produit}</strong>.
            {!rapport.remplit_gabarit && (
              <>
                {" "}
                Rappel&nbsp;: c&apos;est un classeur de resultats, pas la declaration
                officielle de la BCC.
              </>
            )}
          </p>
        )}

        {etat.etat === "echec" && (
          <div
            role="alert"
            className="rounded-lg bg-pop-danger/10 px-3 py-2 text-[13px] leading-relaxed text-pop-danger"
          >
            <p className="font-semibold">
              Aucun document produit
              {etat.statut ? ` (HTTP ${etat.statut})` : ""}.
            </p>
            <p className="mt-0.5">{etat.message}</p>
          </div>
        )}
      </form>
    </section>
  );
}
