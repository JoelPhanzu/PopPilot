/**
 * PopPilot — tableau de bord CREDIT complet (chantiers 1-2, colonnes du DailyTool).
 *
 * Source : GET /credit/tableau-de-bord (engine/tableau_de_bord_credit.py), qui
 * assemble les moteurs valides au centime. Doctrine flux / stock :
 *   - STOCKS a la date de valorisation (encours, PAR, provisions, clients) ;
 *   - FLUX sur [debut ; fin] (decaissements, P15) — periode libre ;
 *   - cout du risque et migrations : arrete M-1 → arrete.
 * Axes : niveau (agence / superviseur / agent / client) + filtres (agence, sexe,
 * produits, duree, client, agent, superviseur). Aucun calcul ici. Un clic sur une
 * ligne du tableau descend d'un niveau (agence → superviseurs → agents → clients).
 * Top N clients (meilleurs / pires) : GET /credit/clients-top, meme selection.
 *
 * Date sans donnees : l'ecran reste debout — message du moteur, selecteur de dates
 * et arretes charges proposes en un clic. Le repli sur l'ancien ecran (/par) ne
 * sert qu'en demonstration ou quand l'API est injoignable.
 *
 * Cloisonnement — trois verrous : RLS Supabase ; filtre agence dans l'API ;
 * cette page, qui n'affiche que ce que l'API a rendu pour le role.
 * Si l'API ne repond pas (ou en demonstration), l'ancien ecran /par +
 * /provisions sert de repli, avec son bandeau de provenance.
 */
import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { Coquille } from "@/composants/Coquille";
import { FournisseurSession } from "@/composants/ContexteSession";
import { CarteIndicateur } from "@/composants/CarteIndicateur";
import { GraphiquePar } from "@/composants/GraphiquePar";
import { TableauAgences } from "@/composants/TableauAgences";
import { BandeauSource } from "@/composants/BandeauSource";
import { BoutonExport } from "@/composants/BoutonExport";
import { BarreFiltresCredit } from "@/composants/BarreFiltresCredit";
import { AvisArrete } from "@/composants/AvisArrete";
import { SelecteurPeriodeCredit } from "@/composants/SelecteurPeriodeCredit";
import { resoudreArrete, type ArreteResolu } from "@/lib/arretes";
import { GraphiqueDecaissementsJour } from "@/composants/GraphiqueDecaissementsJour";
import { GraphiqueComparatif } from "@/composants/GraphiqueComparatif";
import { GraphiqueMigrations } from "@/composants/GraphiqueMigrations";
import { TableauDailyTool } from "@/composants/TableauDailyTool";
import { TableauTopClients } from "@/composants/TableauTopClients";
import { BoutonsExportTableau } from "@/composants/BoutonsExportTableau";
import { sessionCourante } from "@/lib/session";
import { appelerApi } from "@/lib/api";
import { chargerTableauCredit, chargerValeursFiltres, lireFiltres, ARRETE_PAR_DEFAUT } from "@/lib/credit";
import {
  CRITERES_TOP,
  NIVEAU_SUIVANT,
  NIVEAUX_TDB,
  TOP_N,
  requeteTdb,
  type ArretesCredit,
  type TableauDeBordCredit,
  type TopClients,
} from "@/lib/credit-tdb";
import { aAccesTotal } from "@/lib/roles";
import { dateArreteValide, dateLongue, entier, montant, pourcent } from "@/lib/format";

export const metadata: Metadata = {
  title: "Credit — PopPilot",
  description: "Tableau de bord credit : stocks a date, flux sur periode, migrations, par agence, superviseur, agent.",
};

export const dynamic = "force-dynamic";

const pct = (v: number | null | undefined) => (v == null ? null : pourcent(v * 100));

export default async function PageCredit({
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
    redirect("/login?suite=/credit");
  }

  const sp = await searchParams;
  const un = (k: string) => (typeof sp[k] === "string" && dateArreteValide(sp[k] as string) ? (sp[k] as string) : undefined);
  // Arretes charges : la date par defaut est le PLUS RECENT, jamais une date figee.
  const liste = profil.demo ? null : await appelerApi<ArretesCredit>("/credit/arretes", jeton);
  const disponibles = liste?.ok ? liste.donnees.arretes.map((a) => a.date) : [];
  // Regle du calendrier : le dernier arrete enregistre a la date choisie, et c'est sa date qui
  // s'affiche (5 juillet → 30 juin). Les flux suivent alors le mois de cet arrete.
  const saisie = un("arrete");
  const arrete = resoudreArrete(saisie, disponibles) ?? saisie ?? ARRETE_PAR_DEFAUT;
  const resolu: ArreteResolu = {
    arrete, demande: saisie && saisie !== arrete && disponibles.length ? saisie : null,
    disponibles, erreur: null,
  };
  const debut = resolu.demande ? undefined : un("debut");
  const fin = resolu.demande ? undefined : un("fin");
  const niveau = NIVEAUX_TDB.some((n) => n.cle === sp.niveau) ? (sp.niveau as string) : "agence";
  const filtres = lireFiltres(sp);
  const total = aAccesTotal(profil);
  const topN = TOP_N.find((n) => String(n) === sp.top) ?? 10;
  const critere = CRITERES_TOP.find((c) => c.cle === sp.critere)?.cle ?? "encours";
  const q = new URLSearchParams(requeteTdb({ arrete, debut, fin }, { ...filtres, client: undefined }));
  q.set("n", String(topN));
  q.set("critere", critere);

  const [tdb, valeurs, top] = await Promise.all([
    profil.demo
      ? null
      : appelerApi<TableauDeBordCredit>(`/credit/tableau-de-bord?${requeteTdb({ arrete, debut, fin, niveau }, filtres)}`, jeton),
    profil.demo ? Promise.resolve(null) : chargerValeursFiltres(arrete, jeton),
    profil.demo ? Promise.resolve(null) : appelerApi<TopClients>(`/credit/clients-top?${q.toString()}`, jeton),
  ]);

  // L'API a repondu, mais rien pour cette date (ou periode invalide) : l'ecran
  // reste utilisable — message du moteur + dates — au lieu de tomber.
  if (tdb && !tdb.ok && tdb.statut !== null && tdb.statut !== 401) {
    return (
      <FournisseurSession profil={profil}>
        <Coquille profil={profil} actif="/credit">
          <div className="space-y-6">
            <h1 className="text-2xl font-semibold tracking-tight text-pop-encre">Tableau de bord credit</h1>
            <SelecteurPeriodeCredit key={`${arrete}-${debut}-${fin}`} arrete={arrete}
              debut={debut ?? `${arrete.slice(0, 8)}01`} fin={fin ?? arrete} precedent={null}
              disponibles={disponibles} />
            <p role="status" className="rounded-lg border border-pop-alerte/30 bg-pop-alerte/5 px-4 py-3 text-sm text-pop-alerte">
              {tdb.erreur}
              {disponibles.length > 0 && " Choisir un des arretes charges ci-dessus."}
            </p>
          </div>
        </Coquille>
      </FournisseurSession>
    );
  }

  // Repli : demonstration ou API muette → ancien ecran (/par, /provisions), qui le dit.
  if (tdb === null || !tdb.ok) {
    const ancien = await chargerTableauCredit(arrete, profil, jeton);
    return (
      <FournisseurSession profil={profil}>
        <Coquille profil={profil} actif="/credit">
          <div className="space-y-6">
            <h1 className="text-2xl font-semibold tracking-tight text-pop-encre">Tableau de bord credit</h1>
            {tdb && !tdb.ok && (
              <p role="alert" className="rounded-lg border border-pop-danger/30 bg-pop-danger/5 px-4 py-3 text-sm text-pop-danger">
                Tableau de bord complet indisponible : {tdb.erreur}
              </p>
            )}
            <BandeauSource source={ancien.source} erreurApi={ancien.erreurApi} />
            <GraphiquePar lignes={ancien.par.agences} />
            <TableauAgences lignes={ancien.par.agences} provisions={total ? ancien.provisions?.par_agence : null} />
          </div>
        </Coquille>
      </FournisseurSession>
    );
  }

  const t = tdb.donnees;
  const g = t.lignes[0];
  const detail = t.lignes.slice(1);
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
  const niveauLien = (n: string) => lienAvec({ niveau: n });
  // Descente dans le tableau : seules les lignes « actives » se detaillent (un
  // portefeuille orphelin ou gele n'a pas de superviseur ni d'agent a filtrer).
  const suivant = NIVEAU_SUIVANT[t.niveau];
  const liens: Record<string, string> = {};
  if (suivant) {
    for (const l of detail) {
      if (l.statut !== "actif") continue;
      liens[`${l.agence}|${l.designation}`] = lienAvec({
        niveau: suivant.niveau,
        [suivant.filtre]: suivant.filtre === "agence" ? l.agence : l.designation,
        ...(suivant.filtre !== "agence" && total ? { agence: l.agence } : {}),
      });
    }
  }

  return (
    <FournisseurSession profil={profil}>
      <Coquille profil={profil} actif="/credit">
        <div className="space-y-6">
          <header className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <h1 className="text-2xl font-semibold tracking-tight text-pop-encre">Tableau de bord credit</h1>
              <p className="mt-1 text-sm text-pop-gris">
                Stocks au {dateLongue(t.arrete)} · flux du {dateLongue(t.debut)} au {dateLongue(t.fin)} ·{" "}
                {total ? "MICROPOP" : `Agence ${profil.agence ?? "—"}`} · {entier(t.nb_prets_selectionnes)} prets
                selectionnes
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="print:hidden"><BoutonExport domaine="credit" arrete={t.arrete} libelle="Classeur detaille" /></span>
            </div>
          </header>

          <SelecteurPeriodeCredit key={`${t.arrete}-${t.debut}-${t.fin}`} arrete={t.arrete} debut={t.debut} fin={t.fin} precedent={t.precedent}
            disponibles={disponibles} />
          <AvisArrete resolu={resolu} />

          {valeurs && (
            <BarreFiltresCredit key={JSON.stringify(filtres)} valeurs={valeurs} filtres={filtres}
              agenceFixe={total ? null : profil.agence ?? null} />
          )}

          <nav aria-label="Niveau de detail" className="flex flex-wrap items-center gap-2 print:hidden">
            {NIVEAUX_TDB.map((n) => (
              <Link key={n.cle} href={niveauLien(n.cle)}
                className={`rounded-lg px-3 py-1.5 text-sm ${n.cle === t.niveau ? "bg-pop-bleu font-medium text-white" : "border border-pop-bord bg-pop-carte text-pop-gris hover:border-pop-cyan"}`}>
                {n.libelle}
              </Link>
            ))}
            {!t.objectifs_applicables && (
              <span className="text-xs text-pop-alerte">
                Objectifs masques : un filtre sexe / produit / duree / client decoupe le realise, pas l&apos;objectif.
              </span>
            )}
          </nav>

          {t.message && (
            <p role="status" className="rounded-lg border border-pop-alerte/30 bg-pop-alerte/5 px-4 py-3 text-sm text-pop-alerte">
              {t.message}
            </p>
          )}

          <section aria-label="Indicateurs cles" className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <CarteIndicateur vedette accent intitule={`Encours — ${g.designation}`} valeur={`${montant(g.encours)} USD`}
              precision={`${entier(g.nb_credits)} credits · ${entier(g.nb_clients)} clients`}
              note={g.croissance == null ? "Pas d'arrete M-1 charge : croissance non calculee." : `Croissance vs M-1 (${t.precedent}) : ${pct(g.croissance)} — encours M-1 ${montant(g.encours_m1)}.`} />
            <CarteIndicateur intitule="PAR1 · PAR30 · PAR90" valeur={montant(g.par1)}
              precision={`PAR1 ${pct(g.pct_par1)} · PAR30 ${pct(g.pct_par30)} · PAR90 ${pct(g.pct_par90)}`}
              note={`PAR30 ${montant(g.par30)} (norme BCC) · PAR90 ${montant(g.par90)}`} />
            <CarteIndicateur intitule={`Decaissements du ${t.debut.slice(8, 10)}/${t.debut.slice(5, 7)} au ${t.fin.slice(8, 10)}/${t.fin.slice(5, 7)}`}
              valeur={montant(g.decaisse_volume)}
              precision={`${entier(g.decaisse_nombre)} credits${g.pct_realisation_nombre == null ? "" : ` · ${pct(g.pct_realisation_nombre)} de l'objectif nombre`}`}
              note={`GL ${entier(g.decaisse_categories.GL.nombre)} · IL ${entier(g.decaisse_categories.IL.nombre)} · PME (>= 15 000) ${entier(g.decaisse_categories.PME.nombre)} · P15 : ${entier(g.p15)}${g.p15_objectif ? ` / ${entier(g.p15_objectif)}` : ""}${g.productivite == null ? "" : ` · productivite ${g.productivite.toFixed(2)}`}`} />
            <CarteIndicateur intitule="Provisions a date" valeur={g.provisions == null ? "—" : montant(g.provisions)}
              precision={g.provisions == null || !g.encours ? null : `${pourcent((g.provisions / g.encours) * 100)} de l'encours`}
              note={g.provisions == null ? "Reserve aux roles Direction, CDG et Audit." : t.complement_daf_exclu ? "Complement manuel DAF exclu : il est saisi par agence entiere." : "Bareme pret par pret + complements manuels DAF."} />
            <CarteIndicateur intitule="Variation de provision (constituee sur le mois)"
              valeur={g.variation_provision == null ? "—" : montant(g.variation_provision)}
              precision={g.provisions_m1 == null ? null : `Provisions a date ${montant(g.provisions)} − fin M-1 ${montant(g.provisions_m1)}`}
              note={g.provisions == null ? "Reserve aux roles Direction, CDG et Audit." : g.variation_provision == null ? "Aucun arrete M-1 charge : variation indisponible." : "Provision a date − provision de la fin du mois precedent (bareme et complements DAF de chaque date)."} />
            <CarteIndicateur intitule={`Cout du risque (M-1 → ${t.arrete.slice(8, 10)}/${t.arrete.slice(5, 7)})`}
              valeur={g.cout_du_risque == null ? "—" : montant(g.cout_du_risque)}
              precision={g.entree_par_nb == null ? null : `${entier(g.entree_par_nb)} entrees en PAR · ${montant(g.entree_par_montant)}`}
              note="Differentiel de provision pret par pret entre l'arrete M-1 et l'arrete." />
            <CarteIndicateur intitule="Encaissements de la periode"
              valeur={montant(g.interets_encaisses)}
              precision={`interets encaisses · ${entier(g.nb_remboursements)} remboursements`}
              note={g.nb_remboursements === 0
                ? "Aucun fichier « Credits rembourses » importe pour cette periode."
                : `Capital ${montant(g.capital_rembourse)} · penalites ${montant(g.penalites_encaissees)} · recouvre sur les dossiers en retard a M-1 : ${montant(g.recouvre_sur_par)}.`} />
            <CarteIndicateur intitule="Potentiel fin de mois (si rien ne change)"
              valeur={g.potentiel_cout_du_risque == null ? "—" : montant(g.potentiel_cout_du_risque)}
              precision={`${entier(g.potentiel_migration_nb)} credits sains entreraient en PAR · ${montant(g.potentiel_migration_montant)}`}
              note="Cout du risque projete au dernier jour du mois sans aucun recouvrement : les retards vieillissent et changent de tranche ; les credits sains dont une echeance tombe avant la fin du mois entrent en PAR." />
          </section>

          <section className="rounded-xl border border-pop-bord bg-pop-carte p-5 shadow-sm">
            <GraphiqueDecaissementsJour jours={t.decaissements_jour}
              objectifVolume={g.objectif_volume} objectifNombre={g.objectif_nombre} />
          </section>

          <div className="grid gap-6 xl:grid-cols-2">
            {detail.length > 1 && (
              <section className="rounded-xl border border-pop-bord bg-pop-carte p-5 shadow-sm">
                <GraphiqueComparatif lignes={detail} cliquable={total && t.niveau === "agence"} />
              </section>
            )}
            {g.migration_vers && g.entree_par_nb != null && g.cout_du_risque != null && (
              <section className="rounded-xl border border-pop-bord bg-pop-carte p-5 shadow-sm">
                <GraphiqueMigrations entreeNb={g.entree_par_nb} entreeMontant={g.entree_par_montant ?? 0}
                  migrations={g.migration_vers} coutDuRisque={g.cout_du_risque} />
              </section>
            )}
          </div>

          {t.niveau === "client" && t.nb_lignes_total != null && t.nb_lignes_total > detail.length && (
            <p className="text-xs text-pop-gris">
              {entier(detail.length)} plus gros encours affiches sur {entier(t.nb_lignes_total)} clients : filtrer par
              agence, superviseur ou agent pour voir les autres. La ligne MICROPOP couvre toute la selection.
            </p>
          )}
          <TableauDailyTool lignes={t.lignes} liens={liens}
            titre={`DailyTool — par ${NIVEAUX_TDB.find((n) => n.cle === t.niveau)?.libelle.toLowerCase() ?? t.niveau}`}
            exporter={<BoutonsExportTableau domaine="credit" parametres={{ arrete: t.arrete, debut: t.debut, fin: t.fin, niveau: t.niveau }} />} />

          {top?.ok ? (
            <TableauTopClients top={top.donnees}
              exporter={<BoutonsExportTableau domaine="clients" parametres={{ arrete: t.arrete, debut: t.debut, fin: t.fin, n: String(topN), critere }} />}
              lien={(p) => lienAvec({ top: String(p.top ?? topN), critere: p.critere ?? critere })} />
          ) : top && !top.ok ? (
            <p role="status" className="text-sm text-pop-alerte">Top clients indisponible : {top.erreur}</p>
          ) : null}

          <p className="text-xs leading-relaxed text-pop-gris">
            P15 = credits decaisses du {t.p15_periode[0].slice(8, 10)} au {t.p15_periode[1].slice(8, 10)} du mois ; objectif
            P15 = moitie de l&apos;objectif mensuel. Productivite = nombre decaisse / agents du roster. Aux niveaux
            superviseur et agent, un nom absent du roster du mois est regroupe en « portefeuille orphelin » ; une agence
            fermee ou suspendue (non productive, encours toujours actif) en « portefeuille gele ». Clients = noms de
            clients distincts ; credits = dossiers.
            {t.reserves_masques && " Profil agence : provisions, cout du risque et migrations sont reserves a la Direction, au CDG et a l'Audit."}
          </p>
        </div>
      </Coquille>
    </FournisseurSession>
  );
}
