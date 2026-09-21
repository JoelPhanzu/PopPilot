/**
 * PopPilot — tableau de bord COMPTABILITE & INDICATEURS (Phases 2 et 3).
 *
 * Appelle GET /etats-financiers?arrete=… et GET /indicateurs?arrete=… sur
 * l'API FastAPI, qui expose les moteurs valides a ecart nul contre les
 * fichiers reels (engine/etats_financiers.py, engine/indicateurs.py). Aucun
 * agregat, aucun ratio n'est recalcule ici : le front AFFICHE.
 *
 * Cloisonnement : ces deux endpoints sont reserves a ROLES_ACCES_TOTAL cote
 * API. Un role AGENCE ne recoit donc pas un ecran vide, mais l'explication de
 * la regle — le bilan et les ratios prudentiels sont des agregats
 * d'institution, ils ne se decoupent pas par agence.
 *
 * Deux affichages tiennent a la doctrine et ne doivent pas etre "simplifies" :
 *  - le RESULTAT COMPTABLE et le RESULTAT NET sont distingues (§67) ;
 *  - les FONDS PROPRES mis en avant sont la version HORS RESULTAT, celle qui
 *    pilote tous les ratios ; la version resultat affecte reste informative.
 */
import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { Coquille } from "@/composants/Coquille";
import { FournisseurSession } from "@/composants/ContexteSession";
import { CarteIndicateur } from "@/composants/CarteIndicateur";
import { SelecteurArrete } from "@/composants/SelecteurArrete";
import { BandeauSource } from "@/composants/BandeauSource";
import { BoutonExport } from "@/composants/BoutonExport";
import { TableauBilan } from "@/composants/TableauBilan";
import { EtatReferentiel } from "@/composants/EtatReferentiel";
import { TableauResultat } from "@/composants/TableauResultat";
import { TableauIndicateurs } from "@/composants/TableauIndicateurs";
import { TableauAgregats } from "@/composants/TableauAgregats";
import { ReservesComptables } from "@/composants/ReservesComptables";
import { sessionCourante } from "@/lib/session";
import { chargerComptabilite, refusComptabilite } from "@/lib/comptabilite-serveur";
import { bilanDesNormes, type EtatsDetailles, type LigneEtat } from "@/lib/comptabilite";
import { ARRETE_PAR_DEFAUT } from "@/lib/credit";
import { dateArreteValide, dateLongue, entier, montant, part, pourcent } from "@/lib/format";

export const metadata: Metadata = {
  title: "Comptabilite & indicateurs — PopPilot",
  description: "Bilan, compte de resultat et indicateurs prudentiels BCC.",
};

/** Les chiffres dependent de la session : jamais de rendu statique mis en cache. */
export const dynamic = "force-dynamic";

/** Panneau plein ecran : acces impossible, avec la raison. */
function Barrage({ titre, message }: { titre: string; message: string }) {
  return (
    <main className="flex min-h-dvh items-center justify-center bg-pop-bleu px-4">
      <div className="max-w-md rounded-2xl bg-white p-7 shadow-2xl">
        <h1 className="text-lg font-semibold text-pop-encre">{titre}</h1>
        <p className="mt-2 text-sm leading-relaxed text-pop-gris">{message}</p>
        <a href="/login" className="lien-pop mt-4 inline-block text-sm font-medium">
          Retour a la connexion
        </a>
      </div>
    </main>
  );
}


/** Nombre de lignes ELEMENTAIRES d'un etat (les sous-totaux ne se comptent pas). */
function nbLignes(lignes: LigneEtat[]): number {
  return lignes.filter((l) => l.nature === "ligne").length;
}

/**
 * Controles du referentiel — affiches AVANT les etats, pas apres.
 *
 * Trois verifications, et aucune n'est decorative :
 *  - l'ECART AVEC L'AGREGAT confronte deux chemins de calcul independants sur
 *    les memes donnees. Nul, il vaut preuve ; non nul, il signale un compte que
 *    le referentiel ne sait pas placer, et la liste le nomme.
 *  - les COMPTES NON PLACES n'entrent dans aucun total : ils manquent a la
 *    declaration.
 *  - l'EQUILIBRE du bilan. Le fichier magique porte lui-meme un ecart de
 *    quelques milliemes (arrondis sur ~2 000 comptes) ; au-dela, c'est reel.
 */
function ControlesReferentiel({ detail }: { detail: EtatsDetailles }) {
  const c = detail.controles;
  const concordant = Math.abs(c.ecart_avec_agregat) < 0.01;
  const sain = concordant && c.nb_comptes_non_places === 0 && c.equilibre;

  const cadre = sain
    ? "border-pop-ok/30 bg-pop-ok/5"
    : "border-pop-danger/30 bg-pop-danger/5";

  return (
    <section className={`rounded-xl border ${cadre} px-5 py-4`}>
      <h2 className="text-[13px] font-semibold text-pop-encre">
        Controles du referentiel
      </h2>
      <dl className="mt-2 grid grid-cols-1 gap-x-8 gap-y-1.5 sm:grid-cols-2">
        <div className="flex justify-between gap-4">
          <dt className="text-[12px] text-pop-gris">Bilan equilibre (actif − passif)</dt>
          <dd className={`chiffres text-[12px] font-medium ${c.equilibre ? "text-pop-ok" : "text-pop-danger"}`}>
            {montant(c.bilan_equilibre_ecart)}
          </dd>
        </div>
        <div className="flex justify-between gap-4">
          <dt className="text-[12px] text-pop-gris">Ecart avec l&apos;agregat valide</dt>
          <dd className={`chiffres text-[12px] font-medium ${concordant ? "text-pop-ok" : "text-pop-danger"}`}>
            {montant(c.ecart_avec_agregat)}
          </dd>
        </div>
        <div className="flex justify-between gap-4">
          <dt className="text-[12px] text-pop-gris">Comptes de balance lus</dt>
          <dd className="chiffres text-[12px] text-pop-encre">{entier(c.nb_comptes_balance)}</dd>
        </div>
        <div className="flex justify-between gap-4">
          <dt className="text-[12px] text-pop-gris">Comptes non places</dt>
          <dd className={`chiffres text-[12px] font-medium ${c.nb_comptes_non_places === 0 ? "text-pop-ok" : "text-pop-danger"}`}>
            {entier(c.nb_comptes_non_places)}
          </dd>
        </div>
      </dl>

      {!c.equilibre && (
        <p className="mt-2 text-[12px] leading-relaxed text-pop-danger">
          Le bilan ne boucle pas a cet arrete. Tout ce qui en decoule (fonds propres,
          solvabilite, ratios) est a lire avec cette reserve — l&apos;ecart vient de la
          balance importee, pas du referentiel, puisque les deux chemins de calcul
          concordent.
        </p>
      )}
      {c.nb_comptes_non_places > 0 && (
        <p className="mt-2 text-[12px] leading-relaxed text-pop-danger">
          Comptes absents du referentiel&nbsp;: {c.comptes_non_places.slice(0, 20).join(", ")}
          {c.comptes_non_places.length > 20 && ` (+${entier(c.comptes_non_places.length - 20)} autres)`}.
          Ils n&apos;entrent dans aucun total.
        </p>
      )}
    </section>
  );
}

export default async function PageComptabilite({
  searchParams,
}: {
  searchParams: Promise<{ arrete?: string }>;
}) {
  const { profil, jeton, avertissement } = await sessionCourante();

  if (profil === null) {
    if (avertissement) return <Barrage titre="Acces impossible" message={avertissement} />;
    redirect("/login?suite=/comptabilite");
  }

  const { arrete: demande } = await searchParams;
  const arrete =
    typeof demande === "string" && dateArreteValide(demande) ? demande : ARRETE_PAR_DEFAUT;

  // Refus de perimetre : on le DIT, on ne va pas chercher un 403 pour le
  // relayer ensuite comme si l'API etait en panne.
  const refus = refusComptabilite(profil);
  if (refus !== null) {
    return (
      <FournisseurSession profil={profil}>
        <Coquille profil={profil} actif="/comptabilite">
          <div className="max-w-2xl space-y-4">
            <h1 className="text-2xl font-semibold tracking-tight text-pop-encre">
              Comptabilite &amp; indicateurs
            </h1>
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

  const tableau = await chargerComptabilite(arrete, profil, jeton);
  const { etats, detail, indicateurs } = tableau;

  // Le decompte de conformite est le seul chiffre que cette page DERIVE, et il
  // ne derive que des verdicts : il ne cree aucune valeur d'indicateur.
  const normes = indicateurs ? bilanDesNormes(indicateurs.indicateurs) : null;

  const fondsPropresBase = indicateurs?.agregats?.fonds_propres_base ?? null;
  const fondsPropresAvecResultat =
    indicateurs?.agregats?.fonds_propres_base_avec_resultat ?? null;
  const margeNette =
    etats && etats.produits ? part(etats.resultat_net, etats.produits) : null;

  return (
    <FournisseurSession profil={profil}>
      <Coquille profil={profil} actif="/comptabilite">
        <div className="space-y-6">
          <header className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <h1 className="text-2xl font-semibold tracking-tight text-pop-encre">
                Comptabilite &amp; indicateurs
              </h1>
              <p className="mt-1 text-sm text-pop-gris">
                Arrete du {dateLongue(tableau.arrete)} &middot; MICROPOP, toutes agences
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <BoutonExport domaine="comptabilite" arrete={tableau.arrete} />
              <p className="text-xs text-pop-gris">
                Source&nbsp;:{" "}
                {tableau.source === "api"
                ? "moteurs valides (GET /etats-financiers, /indicateurs)"
                : "donnees de demonstration"}
              </p>
            </div>
          </header>

          <SelecteurArrete key={tableau.arrete} arrete={tableau.arrete} />

          {/* Le bandeau porte l'echec des ETATS : sans bilan, l'ecran n'a plus
              de substance. L'echec des seuls indicateurs a son propre message,
              juste en dessous. */}
          <BandeauSource source={tableau.source} erreurApi={tableau.erreurEtats} />

          {/* Les indicateurs peuvent manquer alors que le bilan sort : on le dit
              a part, sinon la moitie de l'ecran disparait sans explication. */}
          {tableau.erreurIndicateurs !== null && etats !== null && (
            <div className="rounded-xl border border-pop-danger/30 bg-pop-danger/5 px-4 py-3 text-sm text-pop-danger">
              <p className="font-semibold">
                Indicateurs prudentiels indisponibles pour cet arrete.
              </p>
              <p className="mt-1 text-[13px] leading-relaxed">{tableau.erreurIndicateurs}</p>
              <p className="mt-1 text-[13px] leading-relaxed">
                Le bilan et le compte de resultat ci-dessous, eux, sont bien ceux du socle.
              </p>
            </div>
          )}

          {etats !== null && (
            <section
              aria-label="Chiffres cles"
              className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4"
            >
              <CarteIndicateur
                vedette
                accent
                intitule="Total du bilan"
                valeur={`${montant(etats.total_actif)} USD`}
                precision={
                  etats.taux_change === null
                    ? "Aucun taux saisi : pas de contre-valeur CDF."
                    : `Taux de l'arrete : ${montant(etats.taux_change)} CDF/USD`
                }
                note="Montants USD : source de verite. Le CDF en est derive au taux date, jamais l'inverse (§43)."
              />
              <CarteIndicateur
                intitule="Resultat net"
                valeur={montant(etats.resultat_net)}
                precision={margeNette === null ? null : `${pourcent(margeNette)} des produits`}
                note={
                  etats.controles.ibp_deduit
                    ? "Apres deduction de l'IBP."
                    : "Resultat comptable : l'IBP n'est du qu'a l'arrete annuel (§67)."
                }
              />
              <CarteIndicateur
                intitule="Fonds propres de base"
                valeur={fondsPropresBase === null ? "—" : montant(fondsPropresBase)}
                precision={
                  fondsPropresAvecResultat === null
                    ? null
                    : `${montant(fondsPropresAvecResultat)} resultat affecte`
                }
                note="Version HORS RESULTAT (comptes 10-14) : c'est elle qui pilote tous les ratios. La version resultat affecte est informative (decision CDG)."
              />
              <CarteIndicateur
                intitule="Conformite aux normes"
                valeur={
                  normes === null
                    ? "—"
                    : `${entier(normes.conformes)} / ${entier(normes.conformes + normes.horsNorme)}`
                }
                precision={
                  normes === null
                    ? null
                    : `${entier(normes.horsNorme)} hors norme · ${entier(normes.sansVerdict)} sans verdict`
                }
                note="Seuls les indicateurs CALCULES et dotes d'une norme lisible recoivent un verdict. Un ratio non calcule n'est jamais compte pour conforme."
              />
            </section>
          )}

          <ReservesComptables etats={etats} indicateurs={indicateurs} />

          {/* LE REFERENTIEL D'ABORD, EN INTEGRALITE. Les 32 lignes de l'actif,
              les 28 du passif, les 26 du compte de resultat : codes BCC,
              sous-totaux, soldes intermediaires et lignes a zero comprises.
              C'est ce qui se declare ; le resume par rubrique vient apres, et
              seulement comme lecture d'ensemble. */}
          {detail !== null && (
            <>
              <ControlesReferentiel detail={detail} />

              <EtatReferentiel
                titre="Bilan — ACTIF"
                sousTitre={`${nbLignes(detail.actif)} lignes du referentiel (V1.F0a), comptes de balance depliables. Montants en ${detail.devise}.`}
                lignes={detail.actif}
                devise={detail.devise}
              />
              <EtatReferentiel
                titre="Bilan — PASSIF"
                sousTitre={`${nbLignes(detail.passif)} lignes du referentiel (V1.F0p). Resultat porte au passif : ${detail.resultat_source}.`}
                lignes={detail.passif}
                devise={detail.devise}
              />
              <EtatReferentiel
                titre="Compte de resultat"
                sousTitre={`${nbLignes(detail.resultat)} lignes du referentiel (V1.F1), soldes intermediaires (80, 82, 83, 84, 85, 87) compris.`}
                lignes={detail.resultat}
                devise={detail.devise}
              />
            </>
          )}

          {detail === null && tableau.erreurDetail !== null && (
            <div className="rounded-xl border border-pop-danger/30 bg-pop-danger/5 px-4 py-3 text-sm text-pop-danger">
              <p className="font-semibold">
                Etats detailles indisponibles : le referentiel ligne a ligne n&apos;a pas pu etre produit.
              </p>
              <p className="mt-1 text-[13px] leading-relaxed">{tableau.erreurDetail}</p>
            </div>
          )}

          {/* Lecture d'ensemble, en complement — jamais en remplacement. */}
          {etats !== null && (
            <>
              <TableauBilan
                actif={etats.actif}
                passif={etats.passif}
                totalActif={etats.total_actif}
                totalPassif={etats.total_passif}
                ecart={etats.controles.bilan_equilibre_ecart}
                resultat={etats.resultat_net}
              />
              <TableauResultat etats={etats} />
            </>
          )}

          {indicateurs !== null && (
            <>
              <TableauIndicateurs donnees={indicateurs} />
              <TableauAgregats agregats={indicateurs.agregats} />
            </>
          )}
        </div>
      </Coquille>
    </FournisseurSession>
  );
}
