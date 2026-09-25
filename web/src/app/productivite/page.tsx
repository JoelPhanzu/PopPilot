/**
 * PopPilot — productivite par agent, superviseur, agence (chantiers 1-2).
 *
 * GET /productivite : encours, PAR30, decaissements du mois et interets ENCAISSES
 * (profitabilite). Les primes ne s'y calculent pas. Aucun chiffre n'est calcule
 * ici — seul le decaissement par agent affiche est celui renvoye par l'API.
 *
 * Regle roster : un agent absent de la liste du mois est regroupe en
 * « PORTEFEUILLE ORPHELIN » par l'API ; sans roster du mois, pas de vue par agent.
 */
import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { Coquille } from "@/composants/Coquille";
import { FournisseurSession } from "@/composants/ContexteSession";
import { AvisArrete } from "@/composants/AvisArrete";
import { arreteAffiche } from "@/lib/arretes";
import { SelecteurArrete } from "@/composants/SelecteurArrete";
import { sessionCourante } from "@/lib/session";
import { appelerApi } from "@/lib/api";
import { dateArreteValide, dateLongue, entier, montant, pourcent } from "@/lib/format";

export const metadata: Metadata = {
  title: "Productivite — PopPilot",
  description: "Interets encaisses, encours, PAR et decaissements par agent, superviseur, agence.",
};

export const dynamic = "force-dynamic";

const NIVEAUX = [
  { cle: "agence", libelle: "Agences" },
  { cle: "superviseur", libelle: "Superviseurs" },
  { cle: "agent", libelle: "Agents de credit" },
] as const;

type Ligne = {
  agence: string;
  designation: string;
  statut: "actif" | "orphelin" | "gele" | "non_rattache";
  encours: number;
  nb_credits: number;
  pct_par30: number;
  decaisse_nombre: number;
  decaisse_volume: number;
  interets_encaisses: number;
  capital_encaisse: number;
  penalites_encaissees: number;
  effectif_agents?: number;
  decaisse_par_agent?: number | null;
};
type Reponse = {
  arrete: string;
  niveau: string;
  roster_du_mois: boolean;
  message?: string;
  lignes: Ligne[];
  totaux?: Record<string, number>;
};

const ETIQUETTE: Record<string, string> = {
  orphelin: "bg-pop-alerte/10 text-pop-alerte",
  gele: "bg-pop-gris/10 text-pop-gris",
  non_rattache: "bg-pop-danger/10 text-pop-danger",
};

function finDuMoisPrecedent(): string {
  const d = new Date();
  return new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), 0)).toISOString().slice(0, 10);
}

export default async function PageProductivite({
  searchParams,
}: {
  searchParams: Promise<{ arrete?: string; niveau?: string }>;
}) {
  const { profil, jeton, avertissement } = await sessionCourante();
  if (profil === null) {
    if (avertissement) redirect("/login");
    redirect("/login?suite=/productivite");
  }
  const sp = await searchParams;
  // Regle du calendrier : dernier arrete credit enregistre a la date choisie.
  const resolu = profil.demo ? null : await arreteAffiche("credit", sp.arrete, jeton);
  const arrete =
    resolu?.arrete ?? (sp.arrete && dateArreteValide(sp.arrete) ? sp.arrete : finDuMoisPrecedent());
  const niveau = NIVEAUX.some((n) => n.cle === sp.niveau) ? (sp.niveau as string) : "agence";
  const r = profil.demo
    ? null
    : await appelerApi<Reponse>(`/productivite?arrete=${arrete}&niveau=${niveau}`, jeton);

  const th = "px-3 py-2.5 text-right text-[12px] font-semibold uppercase tracking-wide text-white/90";
  const td = "chiffres px-3 py-2 text-right text-[13px] text-pop-encre";
  const parAgence = niveau === "agence";

  return (
    <FournisseurSession profil={profil}>
      <Coquille profil={profil} actif="/productivite">
        <div className="space-y-6">
          <header>
            <h1 className="text-2xl font-semibold tracking-tight text-pop-encre">Productivite</h1>
            <p className="mt-1 max-w-3xl text-sm text-pop-gris">
              {dateLongue(arrete)} &middot; interets, capital et penalites ENCAISSES (fichier des
              credits rembourses, rattache par n° de dossier), encours et PAR30 de l&apos;arrete,
              decaissements du mois. Mesure de profitabilite : les primes se calculent ailleurs.
            </p>
          </header>

          <SelecteurArrete key={arrete} arrete={arrete} />
          <AvisArrete resolu={resolu} />

          <nav aria-label="Niveau" className="flex gap-2">
            {NIVEAUX.map((n) => (
              <Link
                key={n.cle}
                href={`?arrete=${arrete}&niveau=${n.cle}`}
                className={`rounded-lg px-3 py-1.5 text-sm ${
                  n.cle === niveau
                    ? "bg-pop-bleu font-medium text-white"
                    : "border border-pop-bord bg-pop-carte text-pop-gris hover:border-pop-cyan"
                }`}
              >
                {n.libelle}
              </Link>
            ))}
          </nav>

          {r === null ? (
            <p className="text-sm text-pop-gris">Indisponible en demonstration.</p>
          ) : !r.ok ? (
            <p role="alert" className="text-sm text-pop-danger">{r.erreur}</p>
          ) : r.donnees.message ? (
            <p role="status" className="rounded-lg border border-pop-alerte/30 bg-pop-alerte/5 px-4 py-3 text-sm text-pop-alerte">
              {r.donnees.message}
            </p>
          ) : (
            <section className="overflow-x-auto rounded-xl border border-pop-bord bg-pop-carte shadow-sm">
              <table className="w-full min-w-[62rem] border-collapse text-sm">
                <thead className="bg-pop-bleu">
                  <tr>
                    <th className={`${th} text-left`}>{parAgence ? "Agence" : "Nom"}</th>
                    {!parAgence && <th className={`${th} text-left`}>Agence</th>}
                    <th className={th}>Interets encaisses</th>
                    <th className={th}>Capital encaisse</th>
                    <th className={th}>Penalites</th>
                    <th className={th}>Encours</th>
                    <th className={th}>Credits</th>
                    <th className={th}>PAR30</th>
                    <th className={th}>Decaisse (nb)</th>
                    <th className={th}>Decaisse (volume)</th>
                    {parAgence && r.donnees.roster_du_mois && <th className={th}>Decaisse / agent</th>}
                  </tr>
                </thead>
                <tbody>
                  {r.donnees.lignes.map((l) => (
                    <tr key={`${l.agence}-${l.designation}`} className="border-b border-pop-bord/60">
                      <td className="px-3 py-2 text-[13px] font-medium text-pop-encre">
                        {l.designation}
                        {l.statut !== "actif" && (
                          <span className={`ml-2 rounded-full px-2 py-0.5 text-[11px] ${ETIQUETTE[l.statut]}`}>
                            {l.statut === "orphelin" ? "hors roster" : l.statut === "gele" ? "agence fermee" : "dossier introuvable"}
                          </span>
                        )}
                      </td>
                      {!parAgence && <td className="px-3 py-2 text-[13px] text-pop-gris">{l.agence}</td>}
                      <td className={`${td} font-semibold`}>{montant(l.interets_encaisses)}</td>
                      <td className={td}>{montant(l.capital_encaisse)}</td>
                      <td className={td}>{montant(l.penalites_encaissees)}</td>
                      <td className={td}>{montant(l.encours)}</td>
                      <td className={td}>{entier(l.nb_credits)}</td>
                      <td className={td}>{pourcent(l.pct_par30 * 100)}</td>
                      <td className={td}>{entier(l.decaisse_nombre)}</td>
                      <td className={td}>{montant(l.decaisse_volume)}</td>
                      {parAgence && r.donnees.roster_du_mois && (
                        <td className={td}>
                          {l.decaisse_par_agent == null ? "—" : montant(l.decaisse_par_agent)}
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
                {r.donnees.totaux && (
                  <tfoot>
                    <tr className="border-t-2 border-pop-bleu font-semibold">
                      <td className="px-3 py-2 text-[13px] text-pop-encre" colSpan={parAgence ? 1 : 2}>
                        Total
                      </td>
                      <td className={td}>{montant(r.donnees.totaux.interets_encaisses)}</td>
                      <td className={td}>{montant(r.donnees.totaux.capital_encaisse)}</td>
                      <td className={td}>{montant(r.donnees.totaux.penalites_encaissees)}</td>
                      <td className={td}>{montant(r.donnees.totaux.encours)}</td>
                      <td className={td}>{entier(r.donnees.totaux.nb_credits)}</td>
                      <td className={td}></td>
                      <td className={td}>{entier(r.donnees.totaux.decaisse_nombre)}</td>
                      <td className={td}>{montant(r.donnees.totaux.decaisse_volume)}</td>
                      {parAgence && r.donnees.roster_du_mois && <td className={td}></td>}
                    </tr>
                  </tfoot>
                )}
              </table>
            </section>
          )}
        </div>
      </Coquille>
    </FournisseurSession>
  );
}
