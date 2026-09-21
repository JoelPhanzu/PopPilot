/**
 * PopPilot — tableau de bord BUDGET (Rapport 4, doctrine figee avec le CDG).
 *
 * Appelle GET /budget?arrete=… , qui expose `engine/budget.py`. Aucun ecart
 * n'est recalcule ici ; les seuls totaux formes a l'ecran sont ceux des
 * groupes charges / produits, sommes sur des lignes deja filtrees.
 *
 * PRINCIPE D'INTEGRITE (CLAUDE.md) : la plateforme s'en tient a la BALANCE,
 * sans retraitement. Les retraitements eventuels se font hors plateforme, sur
 * Excel, a partir des exports. Cet ecran ne propose donc aucun ajustement.
 *
 * TROIS LECTURES, jamais melangees — mensuelle, progression annuelle,
 * realisation a date. Le selecteur les nomme et affiche la question a laquelle
 * chacune repond. La lecture mensuelle disparait (desactivee, avec son motif)
 * quand la balance du mois precedent manque : sans elle, le « realise du
 * mois » vaudrait le cumul depuis janvier.
 */
import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { Coquille } from "@/composants/Coquille";
import { FournisseurSession } from "@/composants/ContexteSession";
import { CarteIndicateur } from "@/composants/CarteIndicateur";
import { SelecteurArrete } from "@/composants/SelecteurArrete";
import { SelecteurNiveauBudget } from "@/composants/SelecteurNiveauBudget";
import { BandeauSource } from "@/composants/BandeauSource";
import { TableauBudget } from "@/composants/TableauBudget";
import { sessionCourante } from "@/lib/session";
import { chargerBudget, refusBudget } from "@/lib/budget-serveur";
import {
  NIVEAUX,
  estCleNiveau,
  grouperParSens,
  nomMois,
  totaliser,
  type CleNiveau,
} from "@/lib/budget";
import { ARRETE_PAR_DEFAUT } from "@/lib/credit";
import { dateArreteValide, dateLongue, montant, pourcent } from "@/lib/format";

export const metadata: Metadata = {
  title: "Budget — PopPilot",
  description: "Suivi budgetaire : realisation du mois, progression annuelle, realisation a date.",
};

export const dynamic = "force-dynamic";

export default async function PageBudget({
  searchParams,
}: {
  searchParams: Promise<{ arrete?: string; niveau?: string }>;
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

  const { arrete: demande, niveau: niveauDemande } = await searchParams;
  const arrete =
    typeof demande === "string" && dateArreteValide(demande) ? demande : ARRETE_PAR_DEFAUT;

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

  // Le niveau demande n'est retenu que s'il est REELLEMENT exploitable : un
  // ?niveau=mensuel dans une URL partagee ne doit pas faire afficher des
  // montants que l'API vient de declarer indisponibles.
  const mensuelOk = b?.niveau_mensuel_disponible ?? false;
  let niveau: CleNiveau = estCleNiveau(niveauDemande) ? niveauDemande : "mensuel";
  if (niveau === "mensuel" && !mensuelOk) niveau = "a_date";
  const lecture = NIVEAUX[niveau];

  // Totaux d'entete : sommes de lignes deja groupees, jamais un total general
  // melangeant charges et produits.
  const groupes = b === null ? [] : grouperParSens(b.lignes);
  const charges = groupes.find((g) => g.sens === "charge");
  const produits = groupes.find((g) => g.sens === "produit");
  const totalCharges = charges ? totaliser(charges.lignes, lecture) : null;
  const totalProduits = produits ? totaliser(produits.lignes, lecture) : null;
  const resultat =
    totalCharges && totalProduits ? totalProduits.realise - totalCharges.realise : null;
  const resultatBudgete =
    totalCharges && totalProduits ? totalProduits.budget - totalCharges.budget : null;

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
            <p className="text-xs text-pop-gris">
              Source&nbsp;:{" "}
              {tableau.source === "api"
                ? "moteur valide (GET /budget)"
                : "donnees de demonstration"}
            </p>
          </header>

          <SelecteurArrete key={tableau.arrete} arrete={tableau.arrete} />

          <BandeauSource source={tableau.source} erreurApi={tableau.erreurApi} />

          {b !== null && (
            <>
              {/* Le motif est affiche EN CLAIR, pas seulement en info-bulle : une
                  lecture manquante s'explique, elle ne se devine pas. */}
              {!mensuelOk && b.motif_mensuel_absent && (
                <div className="rounded-xl border border-pop-alerte/30 bg-pop-alerte/5 px-4 py-3 text-sm text-pop-alerte">
                  <p className="font-semibold">Lecture mensuelle indisponible pour cet arrete.</p>
                  <p className="mt-1 text-[13px] leading-relaxed text-pop-gris">
                    {b.motif_mensuel_absent}
                  </p>
                </div>
              )}

              <SelecteurNiveauBudget
                niveau={niveau}
                mensuelDisponible={mensuelOk}
                motifMensuelAbsent={b.motif_mensuel_absent}
              />

              <section
                aria-label="Totaux de la lecture en cours"
                className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3"
              >
                <CarteIndicateur
                  accent
                  intitule={`Produits — ${lecture.onglet.toLowerCase()}`}
                  valeur={totalProduits === null ? "—" : montant(totalProduits.realise)}
                  precision={
                    totalProduits === null
                      ? null
                      : `${montant(totalProduits.budget)} prevu · ${
                          totalProduits.pct === null ? "—" : pourcent(totalProduits.pct)
                        }`
                  }
                  note={lecture.provenance}
                />
                <CarteIndicateur
                  intitule={`Charges — ${lecture.onglet.toLowerCase()}`}
                  valeur={totalCharges === null ? "—" : montant(totalCharges.realise)}
                  precision={
                    totalCharges === null
                      ? null
                      : `${montant(totalCharges.budget)} prevu · ${
                          totalCharges.pct === null ? "—" : pourcent(totalCharges.pct)
                        }`
                  }
                  note="Depasser le budget de charges est defavorable ; le sous-consommer est favorable. C'est la lecture appliquee aux couleurs du tableau."
                />
                <CarteIndicateur
                  intitule="Solde produits − charges"
                  valeur={resultat === null ? "—" : montant(resultat)}
                  precision={
                    resultatBudgete === null ? null : `${montant(resultatBudgete)} prevu`
                  }
                  note="Difference de deux totaux de la balance, sans aucun retraitement : ce n'est PAS le resultat comptable de l'arrete (voir Comptabilite)."
                />
              </section>

              <TableauBudget lignes={b.lignes} niveau={lecture} />

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
