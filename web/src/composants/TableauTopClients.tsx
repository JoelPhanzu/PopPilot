/**
 * PopPilot — Top N clients : les MEILLEURS (aucun jour de retard, classes par le
 * critere choisi) face aux PIRES (plus gros encours en retard).
 *
 * Source : GET /credit/clients-top (engine/moteur_classement_clients.py), sur la
 * meme selection que le reste de l'ecran (filtres + cloisonnement agence).
 * Le choix Top 10 / 20 / 30 / 50 et le critere vivent dans l'URL (?top=&critere=).
 */
import Link from "next/link";
import type React from "react";
import { entier, montant } from "@/lib/format";
import { CRITERES_TOP, TOP_N, type ClientClasse, type TopClients } from "@/lib/credit-tdb";

const th = "whitespace-nowrap px-2.5 py-2 text-right text-[11px] font-semibold uppercase tracking-wide text-pop-gris";
const td = "chiffres whitespace-nowrap px-2.5 py-1.5 text-right text-[12px] text-pop-encre";

function Tableau({
  titre,
  sousTitre,
  clients,
  colonnes,
  ton,
}: {
  titre: string;
  sousTitre: string;
  clients: ClientClasse[];
  colonnes: { titre: string; valeur: (c: ClientClasse) => string }[];
  ton: "succes" | "danger";
}) {
  return (
    <section className="min-w-0 rounded-xl border border-pop-bord bg-pop-carte shadow-sm">
      <header className="border-b border-pop-bord px-4 py-3">
        <h3 className={`text-sm font-semibold ${ton === "succes" ? "text-pop-bleu" : "text-pop-danger"}`}>{titre}</h3>
        <p className="text-xs text-pop-gris">{sousTitre}</p>
      </header>
      {clients.length === 0 ? (
        <p className="px-4 py-6 text-sm text-pop-gris">Aucun client dans la selection.</p>
      ) : (
        <div className="max-h-[32rem] overflow-auto">
          <table className="w-full border-collapse">
            <thead className="sticky top-0 bg-pop-carte">
              <tr className="border-b border-pop-bord">
                <th className={`${th} text-left`}>#</th>
                <th className={`${th} text-left`}>Client</th>
                {colonnes.map((c) => (
                  <th key={c.titre} className={th}>
                    {c.titre}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {clients.map((c, i) => (
                <tr key={c.numero_client} className="border-b border-pop-bord/60">
                  <td className={`${td} text-left text-pop-gris`}>{i + 1}</td>
                  <td className="px-2.5 py-1.5 text-left text-[12px] text-pop-encre">
                    <span className="font-medium">{c.nom_client ?? c.numero_client}</span>
                    <span className="block text-[11px] text-pop-gris">
                      {c.agence ?? "—"} · {c.agent ?? "—"}
                    </span>
                  </td>
                  {colonnes.map((col) => (
                    <td key={col.titre} className={td}>
                      {col.valeur(c)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

export function TableauTopClients({
  top,
  lien,
  exporter,
}: {
  top: TopClients;
  /** Boutons d'export du classement (fournis par la page). */
  exporter?: React.ReactNode;
  /** Lien vers le meme ecran avec un autre N ou un autre critere. */
  lien: (p: { top?: number; critere?: string }) => string;
}) {
  const libelleCritere = CRITERES_TOP.find((c) => c.cle === top.critere)?.libelle ?? top.critere;
  const valeurMeilleur =
    top.critere === "decaissement"
      ? { titre: "Decaisse (periode)", valeur: (c: ClientClasse) => montant(c.valeur) }
      : top.critere === "fidelite"
        ? { titre: "Credits (historique)", valeur: (c: ClientClasse) => entier(c.valeur) }
        : null;
  const pastille = (actif: boolean) =>
    `rounded-full px-2.5 py-0.5 text-xs ${actif ? "bg-pop-bleu text-white" : "border border-pop-bord text-pop-bleu-2 hover:border-pop-cyan"}`;

  return (
    <section aria-label="Top clients" className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="mr-2 text-lg font-semibold text-pop-encre">Clients : Top {top.n}</h2>
        {TOP_N.map((n) => (
          <Link key={n} href={lien({ top: n })} className={pastille(n === top.n)} scroll={false}>
            Top {n}
          </Link>
        ))}
        <span className="ml-3 text-xs text-pop-gris">Meilleurs classes par :</span>
        {CRITERES_TOP.map((c) => (
          <Link key={c.cle} href={lien({ critere: c.cle })} className={pastille(c.cle === top.critere)} scroll={false}>
            {c.libelle}
          </Link>
        ))}
        <span className="ml-auto text-xs text-pop-gris">{entier(top.nb_clients_selection)} clients dans la selection</span>
        {exporter}
      </div>
      <div className="grid gap-4 xl:grid-cols-2">
        <Tableau
          ton="succes"
          titre={`Top ${top.n} meilleurs clients`}
          sousTitre={`Aucun jour de retard · classes par ${libelleCritere.toLowerCase()}${top.periode ? ` du ${top.periode[0]} au ${top.periode[1]}` : ""}`}
          clients={top.meilleurs}
          colonnes={[
            ...(valeurMeilleur ? [valeurMeilleur] : []),
            { titre: "Encours", valeur: (c) => montant(c.encours) },
            { titre: "Credits", valeur: (c) => entier(c.nb_credits) },
          ]}
        />
        <Tableau
          ton="danger"
          titre={`Top ${top.n} pires clients`}
          sousTitre="Classes par encours en retard (PAR1 du client)"
          clients={top.pires}
          colonnes={[
            { titre: "Encours en retard", valeur: (c) => montant(c.encours_retard) },
            { titre: "Jours de retard", valeur: (c) => entier(c.max_jours_retard) },
            { titre: "Encours", valeur: (c) => montant(c.encours) },
            { titre: "Credits", valeur: (c) => entier(c.nb_credits) },
          ]}
        />
      </div>
    </section>
  );
}
