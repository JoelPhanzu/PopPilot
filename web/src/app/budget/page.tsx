/**
 * PopPilot — tableau de bord BUDGET (Rapport 4, doctrine figee avec le CDG).
 *
 * Appelle GET /budget?arrete=… , qui expose `engine/budget.py`. Aucun ecart
 * n'est recalcule ici ; les seuls totaux formes a l'ecran sont ceux du volet
 * affiche, sommes sur des lignes deja filtrees.
 *
 * PRINCIPE D'INTEGRITE (CLAUDE.md) : la plateforme s'en tient a la BALANCE,
 * sans retraitement. Les retraitements eventuels se font hors plateforme, a
 * partir des exports. Cet ecran ne propose donc aucun ajustement.
 *
 * DEUX AXES, et ils sont independants :
 *
 *  - LE VOLET (charges / produits). Deux suivis distincts, jamais melanges :
 *    additionner une charge et un produit ne donne rien de lisible, et le taux
 *    de realisation calcule sur un tel total serait pire encore.
 *
 *  - LA LECTURE (mensuelle / progression annuelle / realisation a date). Trois
 *    questions differentes, nommees a l'ecran. La lecture mensuelle se desactive
 *    quand la balance du mois precedent manque : sans elle, le « realise du
 *    mois » vaudrait le cumul depuis janvier.
 *
 * ET UN PREALABLE : sans MAPPING compte→ligne, aucun compte de la balance n'est
 * rattache a une ligne budgetaire. Le realise sort alors a 0,00 partout, face a
 * un budget bien charge — le calcul « reussit » et le resultat est faux. Dans ce
 * cas l'ecran n'affiche AUCUN chiffre de realisation : il dit ce qui manque et
 * ou le charger.
 */
import type { Metadata } from "next";
import { redirect } from "next/navigation";
import Link from "next/link";
import { Coquille } from "@/composants/Coquille";
import { FournisseurSession } from "@/composants/ContexteSession";
import { CarteIndicateur } from "@/composants/CarteIndicateur";
import { AvisArrete } from "@/composants/AvisArrete";
import { arreteAffiche } from "@/lib/arretes";
import { SelecteurArrete } from "@/composants/SelecteurArrete";
import { SelecteurNiveauBudget } from "@/composants/SelecteurNiveauBudget";
import { SelecteurVoletBudget } from "@/composants/SelecteurVoletBudget";
import { BandeauSource } from "@/composants/BandeauSource";
import { BoutonExport } from "@/composants/BoutonExport";
import { TableauBudget } from "@/composants/TableauBudget";
import { sessionCourante } from "@/lib/session";
import { chargerBudget, refusBudget } from "@/lib/budget-serveur";
import {
  NIVEAUX,
  VOLETS,
  estCleNiveau,
  estCleVolet,
  lignesDuVolet,
  lignesSansSens,
  nomMois,
  totaliser,
  type CleNiveau,
  type CleVolet,
} from "@/lib/budget";
import { peutEcrire } from "@/lib/roles";
import { ARRETE_PAR_DEFAUT } from "@/lib/credit";
import { dateArreteValide, dateLongue, entier, montant, pourcent } from "@/lib/format";

export const metadata: Metadata = {
  title: "Budget — PopPilot",
  description: "Suivi budgetaire : charges et produits, en trois lectures.",
};

export const dynamic = "force-dynamic";

export default async function PageBudget({
  searchParams,
}: {
  searchParams: Promise<{ arrete?: string; niveau?: string; volet?: string }>;
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
    redirect("/login?suite=/budget");
  }

  const {
    arrete: demande,
    niveau: niveauDemande,
    volet: voletDemande,
  } = await searchParams;
  // Regle du calendrier : le realise vient de la balance → dernier arrete de balance enregistre.
  const resolu = profil.demo ? null : await arreteAffiche("balance", demande, jeton);
  const arrete =
    resolu?.arrete ??
    (typeof demande === "string" && dateArreteValide(demande) ? demande : ARRETE_PAR_DEFAUT);

  const refus = refusBudget(profil);
  if (refus !== null) {
    return (
      <FournisseurSession profil={profil}>
        <Coquille profil={profil} actif="/budget">
          <div className="max-w-2xl space-y-4">
            <h1 className="text-2xl font-semibold tracking-tight text-pop-encre">Budget</h1>
            <div className="rounded-xl border border-pop-bord bg-pop-carte px-5 py-4 shadow-sm">
              <p className="text-[13px] font-semibold text-pop-encre">
                Domaine reserve aux roles d&apos;institution
              </p>
              <p className="mt-1.5 text-[13px] leading-relaxed text-pop-gris">{refus}</p>
              <a href="/credit" className="lien-pop mt-3 inline-block text-[13px] font-medium">
                Aller au tableau de bord credit
              </a>
            </div>
          </div>
        </Coquille>
      </FournisseurSession>
    );
  }

  const tableau = await chargerBudget(arrete, profil, jeton);
  const b = tableau.donnees;

  const mappingOk = b?.mapping_present ?? false;
  const mensuelOk = b?.niveau_mensuel_disponible ?? false;

  // Un ?niveau=mensuel venu d'une URL partagee ne doit pas faire afficher des
  // montants que l'API vient de declarer indisponibles.
  let niveau: CleNiveau = estCleNiveau(niveauDemande) ? niveauDemande : "mensuel";
  if (niveau === "mensuel" && !mensuelOk) niveau = "a_date";
  const lecture = NIVEAUX[niveau];

  const volet: CleVolet = estCleVolet(voletDemande) ? voletDemande : "charges";
  const vue = VOLETS[volet];

  const lignes = b === null ? [] : lignesDuVolet(b.lignes, vue);
  const orphelines = b === null ? [] : lignesSansSens(b.lignes);
  const compte: Record<CleVolet, number> =
    b === null
      ? { charges: 0, produits: 0 }
      : {
          charges: lignesDuVolet(b.lignes, VOLETS.charges).length,
          produits: lignesDuVolet(b.lignes, VOLETS.produits).length,
        };

  // Les cartes sont la SOMME EXACTE des lignes affichees juste en dessous :
  // memes lignes, meme lecture, meme volet. Aucun chiffre d'entete ne vient
  // d'ailleurs que du tableau qu'il coiffe.
  const total = lignes.length > 0 ? totaliser(lignes, lecture) : null;

  return (
    <FournisseurSession profil={profil}>
      <Coquille profil={profil} actif="/budget">
        <div className="space-y-6">
          <header className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <h1 className="text-2xl font-semibold tracking-tight text-pop-encre">Budget</h1>
              <p className="mt-1 text-sm text-pop-gris">
                Arrete du {dateLongue(tableau.arrete)}
                {b !== null && (
                  <>
                    {" "}
                    &middot; exercice {b.exercice}, {nomMois(b.mois)} &middot; hypothese{" "}
                    {b.hypothese}
                  </>
                )}
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <BoutonExport domaine="budget" arrete={tableau.arrete} parametres={{ hypothese: b?.hypothese }} />
              <p className="text-xs text-pop-gris">
                Source&nbsp;:{" "}
                {tableau.source === "api"
                ? "moteur valide (GET /budget)"
                : "donnees de demonstration"}
              </p>
            </div>
          </header>

          <SelecteurArrete key={tableau.arrete} arrete={tableau.arrete} />
          <AvisArrete resolu={resolu} />

          <BandeauSource source={tableau.source} erreurApi={tableau.erreurApi} />

          {b !== null && (
            <>
              {/* PRÉALABLE BLOQUANT : sans mapping, pas de realise. On le dit et
                  on s'arrete la — afficher des 0,00 les ferait prendre pour une
                  sous-consommation totale. */}
              {!mappingOk && (
                <section className="rounded-xl border border-pop-danger/30 bg-pop-danger/5 px-5 py-4">
                  <h2 className="text-[13px] font-semibold text-pop-danger">
                    Realise non calculable : le mapping budgetaire n&apos;est pas charge.
                  </h2>
                  <p className="mt-1.5 text-[13px] leading-relaxed text-pop-gris">
                    {b.motif_realise_absent}
                  </p>
                  <p className="mt-2 text-[13px] leading-relaxed text-pop-gris">
                    Le budget, lui, est bien charge ({entier(b.lignes.length)} lignes
                    budgetaires). Il ne manque que la correspondance compte comptable →
                    ligne budgetaire, sans laquelle la balance ne peut etre rattachee a
                    aucune ligne.
                  </p>
                  {peutEcrire(profil) && (
                    <p className="mt-3 flex flex-wrap gap-4 text-[13px]">
                      <Link href="/import" className="lien-pop font-medium">
                        Importer le fichier de suivi budgetaire (2 feuilles)
                      </Link>
                      <Link href="/configuration" className="lien-pop font-medium">
                        Saisir les affectations a la main
                      </Link>
                    </p>
                  )}
                </section>
              )}

              {!mensuelOk && mappingOk && b.motif_mensuel_absent && (
                <div className="rounded-xl border border-pop-alerte/30 bg-pop-alerte/5 px-4 py-3 text-sm text-pop-alerte">
                  <p className="font-semibold">Lecture mensuelle indisponible pour cet arrete.</p>
                  <p className="mt-1 text-[13px] leading-relaxed text-pop-gris">
                    {b.motif_mensuel_absent}
                  </p>
                </div>
              )}

              {mappingOk && (
                <>
                  <SelecteurVoletBudget volet={volet} compte={compte} />

                  <SelecteurNiveauBudget
                    niveau={niveau}
                    mensuelDisponible={mensuelOk}
                    motifMensuelAbsent={b.motif_mensuel_absent}
                  />

                  <section
                    aria-label={`Totaux — ${vue.onglet}, ${lecture.onglet}`}
                    className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4"
                  >
                    <CarteIndicateur
                      accent
                      intitule={lecture.intituleBudget}
                      valeur={total === null ? "—" : montant(total.budget)}
                      precision={`${entier(lignes.length)} ligne(s) — ${vue.onglet.toLowerCase()}`}
                      note="Somme exacte des lignes budgetaires affichees ci-dessous."
                    />
                    <CarteIndicateur
                      intitule={lecture.intituleRealise}
                      valeur={total === null ? "—" : montant(total.realise)}
                      precision={lecture.provenance}
                      note={`Somme exacte des realises du tableau. Mapping : ${entier(
                        b.nb_comptes_mappes,
                      )} comptes rattaches.`}
                    />
                    <CarteIndicateur
                      intitule="Ecart"
                      valeur={total === null ? "—" : montant(total.ecart)}
                      precision="Realise − budget"
                      note={vue.lecture}
                    />
                    <CarteIndicateur
                      intitule={lecture.intitulePct}
                      valeur={
                        total === null || total.pct === null ? "—" : pourcent(total.pct)
                      }
                      precision={
                        total === null || total.budget === 0
                          ? "Aucun budget sur ce volet : pas de taux."
                          : "Total realise ÷ total budgete"
                      }
                      note="Recalcule sur les TOTAUX, jamais moyenne des taux de chaque ligne : une moyenne de taux donnerait le meme poids a une ligne de 200 et a une ligne de 200 000."
                    />
                  </section>

                  {lignes.length > 0 ? (
                    <TableauBudget lignes={lignes} niveau={lecture} />
                  ) : (
                    <p className="rounded-xl border border-pop-bord bg-pop-carte px-5 py-4 text-[13px] text-pop-gris shadow-sm">
                      Aucune ligne de ce volet pour cet exercice.
                    </p>
                  )}

                  {orphelines.length > 0 && (
                    <section className="rounded-xl border border-pop-alerte/30 bg-pop-alerte/5 px-5 py-4">
                      <h2 className="text-[13px] font-semibold text-pop-alerte">
                        {entier(orphelines.length)} ligne(s) sans sens renseigne
                      </h2>
                      <p className="mt-1 text-[13px] leading-relaxed text-pop-gris">
                        Ces lignes ne sont ni charge ni produit dans le mapping : elles
                        n&apos;entrent dans aucun des deux volets, et donc dans aucun total.
                        Les ranger d&apos;office avec les charges fausserait un total sans
                        que rien ne le signale.
                      </p>
                      <p className="mt-1.5 text-[13px] text-pop-gris">
                        {orphelines.map((l) => l.ligne).join(" · ")}
                      </p>
                    </section>
                  )}
                </>
              )}

              <p className="text-xs leading-relaxed text-pop-gris">
                Principe d&apos;integrite&nbsp;: la plateforme s&apos;en tient a la balance,
                sans retraitement. Les retraitements eventuels se font hors plateforme, a
                partir des exports — ce qui est affiche ici est ce que la comptabilite
                contient.
              </p>
            </>
          )}
        </div>
      </Coquille>
    </FournisseurSession>
  );
}
