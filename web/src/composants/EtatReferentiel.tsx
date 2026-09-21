"use client";

/**
 * PopPilot — un etat financier au format INTEGRAL du referentiel BCC.
 *
 * Aucun resume, aucune omission : toutes les lignes du referentiel sont
 * affichees, dans leur ordre, avec leur code (V1.F0a.03…), leurs sous-totaux,
 * et LES LIGNES A ZERO. Une ligne absente d'une declaration BCC est une
 * anomalie ; la masquer parce qu'elle vaut zero reviendrait a produire une
 * declaration incomplete sans que personne ne le voie.
 *
 * Chaque ligne elementaire s'ouvre sur les COMPTES DE BALANCE qui la composent
 * (numero, libelle, solde) : c'est ce qui permet de justifier un montant
 * devant un controleur sans ressortir la balance.
 *
 * Les lignes en DEDUCTION (provisions pour depreciation, amortissements) sont
 * marquees d'un signe moins explicite : elles s'affichent en positif mais se
 * retranchent de leur sous-total — c'est la convention du referentiel, et le
 * sous-total ne boucle pas autrement.
 */
import { Fragment, useState } from "react";
import { montant } from "@/lib/format";
import { totalComptes, type LigneEtat } from "@/lib/comptabilite";

function Comptes({ ligne }: { ligne: LigneEtat }) {
  if (ligne.comptes.length === 0) {
    return (
      <p className="px-6 py-2 text-[12px] text-pop-gris">
        Aucun compte de balance sur cette ligne a cet arrete.
      </p>
    );
  }
  const total = totalComptes(ligne.comptes);
  return (
    <table className="w-full border-collapse bg-pop-fond/60">
      <caption className="sr-only">Comptes composant la ligne {ligne.code}</caption>
      <tbody className="divide-y divide-pop-bord/60">
        {ligne.comptes.map((c) => (
          <tr key={c.numero_compte}>
            <td className="chiffres py-1.5 pl-10 pr-3 text-left text-[12px] text-pop-gris">
              {c.numero_compte}
            </td>
            <td className="py-1.5 pr-3 text-left text-[12px] text-pop-encre">
              {c.libelle ?? "—"}
            </td>
            <td className="chiffres py-1.5 pr-5 text-right text-[12px] text-pop-encre">
              {montant(c.solde_net)}
            </td>
          </tr>
        ))}
        <tr className="border-t border-pop-bord">
          <td className="py-1.5 pl-10 pr-3 text-left text-[11px] font-medium text-pop-gris" colSpan={2}>
            Somme des soldes de balance ({ligne.comptes.length})
          </td>
          <td className="chiffres py-1.5 pr-5 text-right text-[11px] font-medium text-pop-gris">
            {montant(total)}
          </td>
        </tr>
      </tbody>
    </table>
  );
}

export function EtatReferentiel({
  titre,
  sousTitre,
  lignes,
  devise = "USD",
}: {
  titre: string;
  sousTitre: string;
  lignes: LigneEtat[];
  devise?: string;
}) {
  const [ouvertes, setOuvertes] = useState<Set<string>>(new Set());
  const [toutOuvrir, setToutOuvrir] = useState(false);

  function basculer(code: string) {
    setOuvertes((avant) => {
      const apres = new Set(avant);
      if (apres.has(code)) apres.delete(code);
      else apres.add(code);
      return apres;
    });
  }

  const nbLignes = lignes.filter((l) => l.nature === "ligne").length;

  return (
    <section className="overflow-hidden rounded-xl border border-pop-bord bg-pop-carte shadow-sm">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-pop-bord px-5 py-4">
        <div>
          <h2 className="text-base font-semibold text-pop-encre">{titre}</h2>
          <p className="mt-0.5 text-[13px] text-pop-gris">{sousTitre}</p>
        </div>
        <button
          type="button"
          onClick={() => {
            setToutOuvrir((v) => !v);
            setOuvertes(new Set());
          }}
          className="rounded-lg border border-pop-bord px-3 py-1.5 text-[12px] font-medium text-pop-bleu-2
                     transition hover:bg-pop-fond focus-visible:outline-2 focus-visible:outline-offset-2
                     focus-visible:outline-pop-cyan"
        >
          {toutOuvrir ? "Replier le detail des comptes" : "Deplier le detail des comptes"}
        </button>
      </header>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[42rem] border-collapse">
          <caption className="sr-only">
            {titre} — {nbLignes} lignes du referentiel, montants en {devise}
          </caption>
          <thead className="bg-pop-bleu">
            <tr>
              <th scope="col" className="px-3 py-2.5 text-left text-[12px] font-semibold uppercase tracking-wide text-white/90">
                Code
              </th>
              <th scope="col" className="px-3 py-2.5 text-left text-[12px] font-semibold uppercase tracking-wide text-white/90">
                Libelle
              </th>
              <th scope="col" className="px-5 py-2.5 text-right text-[12px] font-semibold uppercase tracking-wide text-white/90">
                Montant ({devise})
              </th>
            </tr>
          </thead>

          <tbody className="divide-y divide-pop-bord">
            {lignes.map((l) => {
              const estTotal = l.nature === "total_general";
              const estSousTotal = l.nature === "sous_total";
              const ouverte = toutOuvrir !== ouvertes.has(l.code);
              const deduction = l.nature === "ligne" && l.signe < 0;

              const fond = estTotal
                ? "bg-pop-bleu/10"
                : estSousTotal
                  ? "bg-pop-fond"
                  : "";
              const gras = estTotal || estSousTotal ? "font-semibold" : "font-normal";

              return (
                // La cle porte sur le Fragment : deux <tr> par ligne du
                // referentiel (la ligne, et son detail deplie).
                <Fragment key={l.code}>
                  <tr className={`${fond} transition hover:bg-pop-fond/80`}>
                    <td className="chiffres px-3 py-2 text-left text-[11px] text-pop-gris">
                      {l.code}
                    </td>
                    <th scope="row" className="px-3 py-2 text-left">
                      {l.nature === "ligne" ? (
                        <button
                          type="button"
                          onClick={() => basculer(l.code)}
                          aria-expanded={ouverte}
                          className="flex items-start gap-1.5 text-left text-[13px] font-normal text-pop-encre
                                     hover:text-pop-bleu-2 focus-visible:outline-2 focus-visible:outline-offset-2
                                     focus-visible:outline-pop-cyan"
                        >
                          <span aria-hidden className="mt-0.5 text-[10px] text-pop-gris">
                            {ouverte ? "▾" : "▸"}
                          </span>
                          <span>
                            {l.libelle}
                            {deduction && (
                              <span className="ml-1.5 rounded bg-pop-alerte/10 px-1.5 py-0.5 text-[10px] font-medium text-pop-alerte">
                                en deduction
                              </span>
                            )}
                          </span>
                        </button>
                      ) : (
                        <span className={`text-[13px] ${gras} text-pop-encre`}>{l.libelle}</span>
                      )}
                    </th>
                    <td
                      className={`chiffres px-5 py-2 text-right text-[13px] ${gras} ${
                        estTotal ? "text-pop-bleu" : "text-pop-encre"
                      }`}
                    >
                      {montant(l.montant)}
                    </td>
                  </tr>

                  {l.nature === "ligne" && ouverte && (
                    <tr>
                      <td colSpan={3} className="p-0">
                        <Comptes ligne={l} />
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}
