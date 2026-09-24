"use client";

/**
 * PopPilot — envoi d'un grand livre CBS pour produire le fichier SAGE.
 *
 * Meme principe que FormulaireRapport : envoi en JavaScript pour que l'echec
 * s'affiche SOUS le formulaire (le fichier reste selectionne), et le .xlsx est
 * enregistre, jamais ouvert dans un onglet.
 *
 * Le fichier est rendu meme en ALERTE (desequilibre, sens inconnu) : le
 * comptable doit pouvoir l'ouvrir pour comprendre. L'ecran dit alors en clair
 * qu'il n'est PAS importable en l'etat.
 */
import { useState } from "react";
import { montant } from "@/lib/format";

type Bilan = {
  statut: string;
  lignes: number;
  debit: number;
  credit: number;
  ecart: number;
  periode: string;
  alertes: string;
  nom: string;
};

function nomPropose(entete: string | null): string {
  const m = entete ? /filename="?([^";]+)"?/i.exec(entete) : null;
  return m ? m[1] : "GL_SAGE.xlsx";
}

export function FormulaireSage() {
  const [enCours, setEnCours] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);
  const [bilan, setBilan] = useState<Bilan | null>(null);

  async function envoyer(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setErreur(null);
    setBilan(null);
    setEnCours(true);
    try {
      const reponse = await fetch("/api/sage", {
        method: "POST",
        body: new FormData(e.currentTarget),
      });
      if (!reponse.ok) {
        setErreur((await reponse.text()) || `Echec (HTTP ${reponse.status}).`);
        return;
      }
      const h = reponse.headers;
      const nom = nomPropose(h.get("content-disposition"));
      setBilan({
        statut: h.get("x-sage-statut") ?? "?",
        lignes: Number(h.get("x-sage-lignes") ?? 0),
        debit: Number(h.get("x-sage-total-debit") ?? 0),
        credit: Number(h.get("x-sage-total-credit") ?? 0),
        ecart: Number(h.get("x-sage-ecart") ?? 0),
        periode: h.get("x-sage-periode") ?? "",
        alertes: h.get("x-sage-alertes") ?? "",
        nom,
      });
      const lien = document.createElement("a");
      lien.href = URL.createObjectURL(await reponse.blob());
      lien.download = nom;
      lien.click();
      URL.revokeObjectURL(lien.href);
    } catch (x) {
      setErreur(x instanceof Error ? x.message : String(x));
    } finally {
      setEnCours(false);
    }
  }

  const ok = bilan?.statut === "OK";

  return (
    <section className="rounded-xl border border-pop-bord bg-pop-carte p-5 shadow-sm">
      <form onSubmit={envoyer} className="flex flex-wrap items-end gap-4">
        <div>
          <label htmlFor="sage-fichier" className="block text-[12px] font-medium text-pop-gris">
            Grand livre CBS (.xlsx, 9 colonnes)
          </label>
          <input
            id="sage-fichier"
            name="fichier"
            type="file"
            required
            accept=".xlsx,.xlsm"
            className="mt-1 block text-sm text-pop-encre file:mr-3 file:rounded-lg file:border-0 file:bg-pop-fond file:px-3 file:py-1.5 file:text-sm"
          />
        </div>
        <div>
          <label htmlFor="sage-feuille" className="block text-[12px] font-medium text-pop-gris">
            Feuille (facultatif)
          </label>
          <input
            id="sage-feuille"
            name="feuille"
            placeholder="Grand_livre"
            className="mt-1 rounded-lg border border-pop-bord bg-white px-3 py-1.5 text-sm outline-none focus:border-pop-cyan focus:ring-2 focus:ring-pop-cyan/30"
          />
        </div>
        <button
          type="submit"
          disabled={enCours}
          className="rounded-lg bg-pop-bleu px-4 py-2 text-sm font-medium text-white transition hover:bg-pop-bleu-2 disabled:cursor-not-allowed disabled:opacity-45"
        >
          {enCours ? "Traitement…" : "Produire le fichier SAGE"}
        </button>
      </form>

      {erreur && (
        <p
          role="alert"
          className="mt-4 rounded-lg border border-pop-danger/30 bg-pop-danger/5 px-3 py-2 text-sm text-pop-danger"
        >
          {erreur}
        </p>
      )}

      {bilan && (
        <div
          role="status"
          className={`mt-4 rounded-lg border px-4 py-3 text-sm ${
            ok ? "border-pop-ok/30 bg-pop-ok/5" : "border-pop-alerte/40 bg-pop-alerte/5"
          }`}
        >
          <p className={`font-semibold ${ok ? "text-pop-ok" : "text-pop-alerte"}`}>
            {ok
              ? "Fichier equilibre : importable dans SAGE apres saisie des N° piece, code journal et section."
              : "ALERTE : fichier NON importable en l'etat — il est fourni pour analyse."}
          </p>
          <dl className="chiffres mt-2 grid grid-cols-2 gap-x-6 gap-y-1 text-pop-encre sm:grid-cols-4">
            <dt className="text-pop-gris">Lignes</dt>
            <dd>{bilan.lignes.toLocaleString("fr-FR")}</dd>
            <dt className="text-pop-gris">Periode</dt>
            <dd>{bilan.periode || "—"}</dd>
            <dt className="text-pop-gris">Total debit CDF</dt>
            <dd>{montant(bilan.debit)}</dd>
            <dt className="text-pop-gris">Total credit CDF</dt>
            <dd>{montant(bilan.credit)}</dd>
            <dt className="text-pop-gris">Ecart</dt>
            <dd>{montant(bilan.ecart)}</dd>
          </dl>
          {bilan.alertes && <p className="mt-2 text-pop-alerte">{bilan.alertes}</p>}
          <p className="mt-2 text-xs text-pop-gris">Enregistre sous {bilan.nom}.</p>
        </div>
      )}
    </section>
  );
}
