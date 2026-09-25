/**
 * PopPilot — tableau de bord EPARGNE (meme exigence que le credit).
 *
 * Deux sources, aucun calcul ici :
 *   - GET /epargne/tableau-de-bord (engine/tableau_de_bord_epargne.py) : stocks a
 *     l'inventaire de l'arrete, FLUX (depots, retraits) sur [debut ; fin] par mois
 *     entiers, M-1, couverture epargne / credit ; par agence, produit, type ou
 *     client ; filtres devise, type, titulaire, groupes. Cloisonne : un role AGENCE
 *     ne voit que son agence.
 *   - GET /epargne (synthese validee, 169 799 comptes) : ventilation par type et
 *     par devise d'origine — roles d'institution seulement.
 *
 * Le point de vigilance est l'UNITE : l'encours, les depots et les retraits sont
 * des USD homogenes (CDF converti au taux du mois) ; les colonnes « d'origine »
 * restent en devise d'emission et ne s'additionnent pas entre elles.
 * Une date sans inventaire affiche le message du moteur et les inventaires
 * charges, sans casser l'ecran.
 */
import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { Coquille } from "@/composants/Coquille";
import { FournisseurSession } from "@/composants/ContexteSession";
import { CarteIndicateur } from "@/composants/CarteIndicateur";
import { BandeauSource } from "@/composants/BandeauSource";
import { BoutonExport } from "@/composants/BoutonExport";
import { VentilationEpargne } from "@/composants/VentilationEpargne";
import { TableauEpargneDevises } from "@/composants/TableauEpargneDevises";
import { AvisArrete } from "@/composants/AvisArrete";
import { SelecteurPeriodeCredit } from "@/composants/SelecteurPeriodeCredit";
import { arreteAffiche } from "@/lib/arretes";
import { GraphiqueEpargne } from "@/composants/GraphiqueEpargne";
import { TableauEpargneTdb } from "@/composants/TableauEpargneTdb";
import { BoutonsExportTableau } from "@/composants/BoutonsExportTableau";
import { sessionCourante } from "@/lib/session";
import { appelerApi } from "@/lib/api";
import { chargerEpargne } from "@/lib/epargne-serveur";
import { soldeMoyen } from "@/lib/epargne";
import {
  CLES_FILTRES_EPARGNE,
  FILTRES_EPARGNE,
  NIVEAUX_EPARGNE,
  type TableauDeBordEpargne,
  type TopEpargnants,
} from "@/lib/epargne-tdb";
import { aAccesTotal } from "@/lib/roles";
import { dateArreteValide, dateLongue, entier, montant, part, pourcent } from "@/lib/format";

export const metadata: Metadata = {
  title: "Epargne — PopPilot",
  description: "Epargne : encours, collecte (depots / retraits) sur periode, couverture du credit, par agence, produit, type, client.",
};

export const dynamic = "force-dynamic";

const TOPS = [10, 20, 30, 50] as const;

export default async function PageEpargne({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const { profil, jeton, avertissement } = await sessionCourante();

  if (profil === null) {
    if (avertissement) {
      return (
        <main className="flex min-h-dvh items-center justify-center bg-pop-bleu px-4">
          <div className="max-w-md rounded-2xl bg-white p-7 shadow-2xl">
            <h1 className="text-lg font-semibold text-pop-encre">Acces impossible</h1>
            <p className="mt-2 text-sm leading-relaxed text-pop-gris">{avertissement}</p>
            <a href="/login" className="lien-pop mt-4 inline-block text-sm font-medium">
              Retour a la connexion
            </a>
          </div>
        </main>
      );
    }
    redirect("/login?suite=/epargne");
  }

  const sp = await searchParams;
  const un = (k: string) => {
    const v = sp[k];
    const s = Array.isArray(v) ? v[0] : v;
    return s && s.trim() ? s.trim() : undefined;
  };
  const date = (k: string) => {
    const v = un(k);
    return v && dateArreteValide(v) ? v : undefined;
  };
  const total = aAccesTotal(profil);
  const niveau = NIVEAUX_EPARGNE.some((x) => x.cle === un("niveau")) ? (un("niveau") as string) : "agence";
  const topN = TOPS.find((x) => String(x) === un("top")) ?? 10;

  // Regle du calendrier : dernier inventaire enregistre a la date choisie (5 juillet → 30 juin),
  // et c'est sa date qui s'affiche ; les flux suivent alors le mois de cet arrete.
  const resolu = profil.demo ? null : await arreteAffiche("epargne", date("arrete"), jeton);
  const arreteResolu = resolu?.arrete ?? date("arrete");
  const flux = (k: string) => (resolu?.demande ? undefined : date(k));
  const q = new URLSearchParams();
  for (const [k, v] of [["arrete", arreteResolu], ["debut", flux("debut")], ["fin", flux("fin")]] as const) {
    if (v) q.set(k, v);
  }
  q.set("niveau", niveau);
  for (const k of CLES_FILTRES_EPARGNE) {
    const v = un(k);
    if (v) q.set(k, v);
  }

  const tdb = profil.demo ? null : await appelerApi<TableauDeBordEpargne>(`/epargne/tableau-de-bord?${q.toString()}`, jeton);

  const lienAvec = (modifs: Record<string, string | undefined>) => {
    const u = new URLSearchParams();
    for (const [k, v] of Object.entries(sp)) {
      if (Array.isArray(v)) v.forEach((x) => u.append(k, x));
      else if (v) u.set(k, v);
    }
    for (const [k, v] of Object.entries(modifs)) {
      if (v) u.set(k, v);
      else u.delete(k);
    }
    return `?${u.toString()}`;
  };

  // Demonstration ou API muette : l'ancienne synthese (avec son bandeau de provenance).
  if (tdb === null || (!tdb.ok && tdb.statut === null)) {
    const arrete = arreteResolu ?? "2026-08-31";
    const ancien = total ? await chargerEpargne(arrete, profil, jeton) : null;
    return (
      <FournisseurSession profil={profil}>
        <Coquille profil={profil} actif="/epargne">
          <div className="space-y-6">
            <h1 className="text-2xl font-semibold tracking-tight text-pop-encre">Epargne</h1>
            {tdb && !tdb.ok && (
              <p role="alert" className="rounded-lg border border-pop-danger/30 bg-pop-danger/5 px-4 py-3 text-sm text-pop-danger">
                {tdb.erreur}
              </p>
            )}
            {ancien && <BandeauSource source={ancien.source} erreurApi={ancien.erreurApi} />}
            {ancien?.donnees && (
              <VentilationEpargne parType={ancien.donnees.par_type} total={ancien.donnees.encours_total} />
            )}
          </div>
        </Coquille>
      </FournisseurSession>
    );
  }

  // L'API a repondu sans donnees (date sans inventaire, periode inversee…) : l'ecran reste debout.
  if (!tdb.ok) {
    const arrete = arreteResolu ?? "2026-08-31";
    return (
      <FournisseurSession profil={profil}>
        <Coquille profil={profil} actif="/epargne">
          <div className="space-y-6">
            <h1 className="text-2xl font-semibold tracking-tight text-pop-encre">Epargne</h1>
            <SelecteurPeriodeCredit key={`${arrete}-${flux("debut")}-${flux("fin")}`} arrete={arrete}
              debut={flux("debut") ?? `${arrete.slice(0, 8)}01`} fin={flux("fin") ?? arrete} precedent={null} />
            <p role="status" className="rounded-lg border border-pop-alerte/30 bg-pop-alerte/5 px-4 py-3 text-sm text-pop-alerte">
              {tdb.erreur}
            </p>
          </div>
        </Coquille>
      </FournisseurSession>
    );
  }

  const t = tdb.donnees;
  const g = t.lignes[0];
  const detail = t.lignes.slice(1);
  const [synthese, top] = await Promise.all([
    total ? chargerEpargne(t.arrete, profil, jeton) : Promise.resolve(null),
    appelerApi<TopEpargnants>(
      `/epargne/top?${new URLSearchParams({ arrete: t.arrete, n: String(topN), ...Object.fromEntries(
        CLES_FILTRES_EPARGNE.flatMap((k) => (un(k) ? [[k, un(k) as string]] : [])),
      ) }).toString()}`,
      jeton,
    ),
  ]);
  const e = synthese?.donnees ?? null;

  // Descente : agence → ses clients ; produit / type → leurs agences.
  const liens: Record<string, string> = {};
  for (const l of detail) {
    if (!l.cle) continue;
    if (niveau === "agence") liens[l.cle] = lienAvec({ niveau: "client", agence: l.cle });
    else if (niveau === "type") liens[l.cle] = lienAvec({ niveau: "agence", type_depot: l.cle });
  }
  const pastille = (actif: boolean) =>
    `rounded-full px-2.5 py-0.5 text-xs ${actif ? "bg-pop-bleu text-white" : "border border-pop-bord text-pop-bleu-2 hover:border-pop-cyan"}`;
  const moyen = soldeMoyen(g.encours, g.nb_epargnants);

  return (
    <FournisseurSession profil={profil}>
      <Coquille profil={profil} actif="/epargne">
        <div className="space-y-6">
          <header className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <h1 className="text-2xl font-semibold tracking-tight text-pop-encre">Tableau de bord epargne</h1>
              <p className="mt-1 text-sm text-pop-gris">
                Stocks au {dateLongue(t.arrete)} · flux du {dateLongue(t.debut)} au {dateLongue(t.fin)} ·{" "}
                {g.designation} · taux {montant(t.taux_change)} CDF/USD
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <BoutonsExportTableau domaine="epargne" parametres={{ arrete: t.arrete, debut: t.debut, fin: t.fin, niveau: t.niveau }} />
              {total && <span className="print:hidden"><BoutonExport domaine="epargne" arrete={t.arrete} libelle="Classeur detaille" /></span>}
            </div>
          </header>

          <SelecteurPeriodeCredit key={`${t.arrete}-${t.debut}-${t.fin}`} arrete={t.arrete} debut={t.debut} fin={t.fin}
            precedent={t.precedent} disponibles={t.inventaires_disponibles} />
          <AvisArrete resolu={resolu} />

          <section aria-label="Filtres" className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-xl border border-pop-bord bg-pop-carte px-4 py-3 shadow-sm print:hidden">
            {FILTRES_EPARGNE.map((f) => (
              <div key={f.cle} className="flex flex-wrap items-center gap-1.5">
                <span className="text-xs text-pop-gris">{f.libelle} :</span>
                <Link href={lienAvec({ [f.cle]: undefined })} className={pastille(!un(f.cle))} scroll={false}>
                  Tous
                </Link>
                {f.valeurs.map(([v, lib]) => (
                  <Link key={v} href={lienAvec({ [f.cle]: v })} className={pastille(un(f.cle) === v)} scroll={false}>
                    {lib}
                  </Link>
                ))}
              </div>
            ))}
            {total && un("agence") && (
              <Link href={lienAvec({ agence: undefined })} className="text-xs lien-pop">
                Retirer le filtre agence ({un("agence")})
              </Link>
            )}
          </section>

          <nav aria-label="Niveau de detail" className="flex flex-wrap items-center gap-2 print:hidden">
            {NIVEAUX_EPARGNE.map((x) => (
              <Link key={x.cle} href={lienAvec({ niveau: x.cle })}
                className={`rounded-lg px-3 py-1.5 text-sm ${x.cle === t.niveau ? "bg-pop-bleu font-medium text-white" : "border border-pop-bord bg-pop-carte text-pop-gris hover:border-pop-cyan"}`}>
                {x.libelle}
              </Link>
            ))}
          </nav>

          {t.message && (
            <p role="status" className="rounded-lg border border-pop-alerte/30 bg-pop-alerte/5 px-4 py-3 text-sm text-pop-alerte">
              {t.message}
            </p>
          )}

          <section aria-label="Indicateurs cles" className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <CarteIndicateur vedette accent intitule={`Encours epargne — ${g.designation}`} valeur={`${montant(g.encours)} USD`}
              precision={`${entier(g.nb_comptes)} comptes · ${entier(g.nb_epargnants)} epargnants`}
              note={`USD d'origine ${montant(g.encours_usd_origine)} · CDF d'origine ${montant(g.encours_cdf_origine)} (converti au taux de l'arrete).${g.croissance == null ? "" : ` Croissance vs M-1 : ${pourcent(g.croissance * 100)}.`}`} />
            <CarteIndicateur intitule="Collecte de la periode" valeur={montant(g.collecte_nette)}
              precision={`depots ${montant(g.depots)} · retraits ${montant(g.retraits)}`}
              note={`Mois lus : ${t.mois_de_flux.length ? t.mois_de_flux.map((d) => d.slice(0, 7)).join(", ") : "aucun"}. ${entier(g.nb_depots)} comptes avec depot, ${entier(g.nb_retraits)} avec retrait.`} />
            <CarteIndicateur intitule="Couverture du credit" valeur={g.couverture_credit == null ? "—" : pourcent(g.couverture_credit * 100)}
              precision={g.encours_credit == null ? null : `epargne / encours credit ${montant(g.encours_credit)}`}
              note="Critere des primes support : epargne >= 60 % de l'encours credit de l'agence. Non calculee sous un filtre devise, type, titulaire ou groupe." />
            <CarteIndicateur intitule="Solde moyen par epargnant" valeur={moyen === null ? "—" : montant(moyen)}
              precision={`${entier(g.nb_comptes_crediteurs)} comptes crediteurs (${pourcent((part(g.nb_comptes_crediteurs, g.nb_comptes) ?? 0))})`}
              note="Encours divise par le nombre d'epargnants distincts." />
          </section>

          <div className="grid gap-6 xl:grid-cols-2">
            {detail.length > 1 && (
              <section className="rounded-xl border border-pop-bord bg-pop-carte p-5 shadow-sm">
                <GraphiqueEpargne lignes={detail} cliquable={total && t.niveau === "agence"} />
              </section>
            )}
            <section className="rounded-xl border border-pop-bord bg-pop-carte p-5 shadow-sm">
              <h2 className="text-sm font-semibold text-pop-encre">Repartition par type de depot (USD)</h2>
              <div className="mt-3">
                <VentilationEpargne parType={{ a_vue: g.a_vue, a_terme: g.a_terme, obligatoire: g.obligatoire }} total={g.encours} />
              </div>
            </section>
          </div>

          {t.niveau === "client" && t.nb_lignes_total > detail.length && (
            <p className="text-xs text-pop-gris">
              {entier(detail.length)} plus gros soldes affiches sur {entier(t.nb_lignes_total)} epargnants : filtrer par
              agence pour voir les autres. La premiere ligne couvre toute la selection.
            </p>
          )}
          <TableauEpargneTdb lignes={t.lignes} liens={liens} />

          {top.ok && (
            <section aria-label="Top epargnants" className="space-y-3">
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="mr-2 text-lg font-semibold text-pop-encre">Top {topN} epargnants</h2>
                {TOPS.map((x) => (
                  <Link key={x} href={lienAvec({ top: String(x) })} className={pastille(x === topN)} scroll={false}>
                    Top {x}
                  </Link>
                ))}
              </div>
              <div className="overflow-x-auto rounded-xl border border-pop-bord bg-pop-carte shadow-sm">
                <table className="w-full min-w-[28rem] border-collapse text-[12px]">
                  <thead>
                    <tr className="border-b border-pop-bord text-pop-gris">
                      <th className="px-3 py-2 text-left">#</th>
                      <th className="px-3 py-2 text-left">Client (id)</th>
                      <th className="px-3 py-2 text-left">Agence</th>
                      <th className="px-3 py-2 text-right">Comptes</th>
                      <th className="px-3 py-2 text-right">Solde (USD)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {top.donnees.clients.map((c, i) => (
                      <tr key={c.id_client} className="border-b border-pop-bord/60">
                        <td className="chiffres px-3 py-1.5 text-pop-gris">{i + 1}</td>
                        <td className="chiffres px-3 py-1.5 text-pop-encre">{c.id_client}</td>
                        <td className="px-3 py-1.5 text-pop-encre">{c.agence ?? "—"}</td>
                        <td className="chiffres px-3 py-1.5 text-right">{entier(c.nb_comptes)}</td>
                        <td className="chiffres px-3 py-1.5 text-right font-medium">{montant(c.solde_usd)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}

          {e && (
            <section className="space-y-3">
              <h2 className="text-lg font-semibold text-pop-encre">Synthese institutionnelle (devises d&apos;origine)</h2>
              <TableauEpargneDevises parTypeDevise={e.par_type_devise} parDeviseOrigine={e.par_devise_origine}
                taux={e.taux_change} encoursTotal={e.encours_total} />
            </section>
          )}

          <p className="text-xs leading-relaxed text-pop-gris">
            Les flux d&apos;epargne viennent de l&apos;inventaire mensuel : la periode se lit par mois entiers, chaque mois
            converti a son taux. Epargnants = clients distincts (ils ne s&apos;additionnent pas d&apos;une ligne a l&apos;autre).
            Titulaire : code 1 = homme, 2 = femme, non renseigne = personne morale ou groupe.
          </p>
        </div>
      </Coquille>
    </FournisseurSession>
  );
}
