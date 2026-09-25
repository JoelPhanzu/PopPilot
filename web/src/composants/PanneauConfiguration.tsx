"use client";

/**
 * PopPilot — panneau de saisie des intrants (DAF / CDG).
 *
 * Cinq sections, chacune avec sa raison d'etre affichee a l'ecran et non
 * seulement en commentaire : quelqu'un qui saisit un taux doit lire, au moment
 * de le saisir, ce qui en depend. Un formulaire muet invite a remplir sans
 * comprendre, et c'est ainsi qu'on fige un taux perime.
 *
 * Aucune validation metier n'est refaite ici : l'API est le seul endroit ou
 * elle vaut pour tous les appelants. Le front se contente de ne pas proposer
 * l'absurde (un select de statuts, un pas de saisie coherent) et d'AFFICHER le
 * refus quand il vient.
 */
import { useActionState } from "react";
import { useFormStatus } from "react-dom";
import { ExportSections } from "@/composants/ExportSections";
import {
  ETAT_CONFIGURATION_INITIAL,
  EFFET_STATUT,
  LIBELLES_STATUT,
  STATUTS_AGENCE,
  fractionVersPourcent,
  type Agence,
  type ConfigurationArrete,
  type EtatConfiguration,
  type MappingBudget,
} from "@/lib/configuration";
import { dateLongue, entier, montant, pourcent } from "@/lib/format";
import {
  enregistrerAgence,
  enregistrerMapping,
  enregistrerProvision,
  enregistrerReintegration,
  enregistrerTaux,
  supprimerMapping,
  supprimerProvision,
  supprimerReintegration,
} from "@/app/configuration/actions";

type Action = (
  precedent: EtatConfiguration,
  donnees: FormData,
) => Promise<EtatConfiguration>;

const champ =
  "mt-1 w-full rounded-lg border border-pop-bord bg-white px-3 py-2 text-sm text-pop-encre " +
  "focus:border-pop-cyan focus:outline-none focus-visible:ring-2 focus-visible:ring-pop-cyan/40";

function Bouton({ libelle, discret = false }: { libelle: string; discret?: boolean }) {
  const { pending } = useFormStatus();
  return (
    <button
      type="submit"
      disabled={pending}
      className={
        (discret
          ? "rounded-lg border border-pop-bord px-3 py-1.5 text-[12px] font-medium text-pop-danger hover:bg-pop-danger/5"
          : "rounded-lg bg-pop-bleu px-5 py-2.5 text-sm font-medium text-white hover:bg-pop-bleu-2") +
        " transition focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-pop-cyan" +
        " disabled:cursor-progress disabled:opacity-60"
      }
    >
      {pending ? "Enregistrement…" : libelle}
    </button>
  );
}

function Retour({ etat }: { etat: EtatConfiguration }) {
  if (etat.etat === "vierge") return null;
  const succes = etat.etat === "succes";
  return (
    <p
      role="status"
      className={
        "mt-3 rounded-lg px-3 py-2 text-[13px] leading-relaxed " +
        (succes
          ? "bg-pop-ok/10 text-pop-ok"
          : "bg-pop-danger/10 text-pop-danger")
      }
    >
      {etat.message}
    </p>
  );
}

function Section({
  titre,
  pourquoi,
  children,
}: {
  titre: string;
  pourquoi: string;
  children: React.ReactNode;
}) {
  return (
    <section className="overflow-hidden rounded-xl border border-pop-bord bg-pop-carte shadow-sm">
      <header className="border-b border-pop-bord px-5 py-4">
        <h2 className="text-base font-semibold text-pop-encre">{titre}</h2>
        <p className="mt-0.5 text-[13px] leading-relaxed text-pop-gris">{pourquoi}</p>
      </header>
      <div className="px-5 py-4">{children}</div>
    </section>
  );
}

/** Un formulaire d'action avec son retour, sans repeter le cablage. */
function Formulaire({
  action,
  children,
  libelle,
  discret = false,
  enLigne = false,
}: {
  action: Action;
  children?: React.ReactNode;
  libelle: string;
  discret?: boolean;
  enLigne?: boolean;
}) {
  const [etat, envoyer] = useActionState(action, ETAT_CONFIGURATION_INITIAL);
  return (
    <form action={envoyer} className={enLigne ? "" : "space-y-3"}>
      {children}
      <Bouton libelle={libelle} discret={discret} />
      {!enLigne && <Retour etat={etat} />}
    </form>
  );
}

/* ════════════════════════════════════════════════════════════════════════ */

export function PanneauConfiguration({
  arrete,
  parametres,
  mapping,
  agences,
}: {
  arrete: string;
  parametres: ConfigurationArrete | null;
  mapping: MappingBudget | null;
  agences: Agence[];
}) {
  const taux = parametres?.taux_change ?? null;

  return (
    <div className="space-y-6">
      {/* ── 1. TAUX DE CHANGE ───────────────────────────────────────────── */}
      <Section
        titre="Taux de change USD → CDF"
        pourquoi={
          "Publie par la BCC : il ne se deduit d'aucune donnee du socle. Sans lui, la " +
          "plateforme REFUSE de produire un montant en CDF plutot que de figer un taux — " +
          "un taux fige donnerait un bilan faux d'un facteur ~2268 sans lever la moindre alerte."
        }
      >
        {taux === null ? (
          <p className="mb-4 rounded-lg bg-pop-danger/10 px-3 py-2 text-[13px] text-pop-danger">
            Aucun taux en vigueur au {dateLongue(arrete)}. Les montants en CDF (FINA, AML)
            ne peuvent pas etre produits pour cet arrete.
          </p>
        ) : (
          <p
            className={
              "mb-4 rounded-lg px-3 py-2 text-[13px] " +
              (taux.du_mois_de_l_arrete
                ? "bg-pop-ok/10 text-pop-ok"
                : "bg-pop-alerte/10 text-pop-alerte")
            }
          >
            Taux applique&nbsp;: <span className="chiffres font-medium">{montant(taux.taux)}</span>{" "}
            CDF/USD, a effet du {dateLongue(taux.date_effet)}.
            {!taux.du_mois_de_l_arrete && (
              <>
                {" "}
                Ce taux n&apos;est PAS celui du mois de l&apos;arrete : le calcul passe, mais
                les montants CDF sont faux de quelques dixiemes de pour cent — un ecart qui
                ne se voit qu&apos;au rapprochement.
              </>
            )}
          </p>
        )}

        <Formulaire action={enregistrerTaux} libelle="Enregistrer le taux">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <label className="block">
              <span className="text-sm font-medium text-pop-encre">Date d&apos;effet</span>
              <input type="date" name="date_effet" required className={champ} />
              <span className="mt-1 block text-[11px] text-pop-gris">
                Le taux vaut a partir de cette date, jusqu&apos;au suivant.
              </span>
            </label>
            <label className="block">
              <span className="text-sm font-medium text-pop-encre">Taux (CDF pour 1 USD)</span>
              <input
                type="text"
                inputMode="decimal"
                name="taux"
                required
                placeholder="2268,75"
                className={`chiffres ${champ}`}
              />
            </label>
          </div>
        </Formulaire>

        {parametres && parametres.taux_historique.length > 0 && (
          <details className="mt-4">
            <summary className="cursor-pointer text-[13px] font-medium text-pop-bleu-2">
              Historique des taux saisis ({entier(parametres.taux_historique.length)})
            </summary>
            <ul className="mt-2 space-y-1">
              {parametres.taux_historique.map((t) => (
                <li key={t.id} className="flex justify-between text-[12px] text-pop-gris">
                  <span>{dateLongue(t.date_effet)}</span>
                  <span className="chiffres">{montant(t.taux)} CDF/USD</span>
                </li>
              ))}
            </ul>
          </details>
        )}
      </Section>

      {/* ── 2. PROVISION MANUELLE ───────────────────────────────────────── */}
      <Section
        titre="Provision speciale par agence (decision DAF)"
        pourquoi={
          "Le 1 %/mois cumule de l'agence fermee de GOMA n'est PAS calcule par l'outil : " +
          "c'est un prelevement decide par les comptables avec l'accord du DAF. Le montant " +
          "saisi REMPLACE le bareme automatique pour cette agence — c'est ce qui evite le " +
          "double comptage. Il est trace : qui l'a saisi, et quand."
        }
      >
        {parametres && parametres.provisions_manuelles.length > 0 ? (
          <ul className="mb-4 divide-y divide-pop-bord rounded-lg border border-pop-bord">
            {parametres.provisions_manuelles.map((p) => (
              <li key={p.agence} className="flex flex-wrap items-center justify-between gap-3 px-3 py-2.5">
                <div className="min-w-0">
                  <p className="text-[13px] font-medium text-pop-encre">{p.agence}</p>
                  <p className="text-[11px] text-pop-gris">
                    {p.note || "Sans note"}
                    {p.saisi_par && ` — saisi par ${p.saisi_par}`}
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  <span className="chiffres text-[13px] text-pop-encre">{montant(p.montant)}</span>
                  <Formulaire action={supprimerProvision} libelle="Retirer" discret enLigne>
                    <input type="hidden" name="agence" value={p.agence} />
                    <input type="hidden" name="date_arrete" value={arrete} />
                  </Formulaire>
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <p className="mb-4 text-[13px] text-pop-gris">
            Aucune provision manuelle pour l&apos;arrete du {dateLongue(arrete)} : le bareme
            automatique s&apos;applique a toutes les agences.
          </p>
        )}

        <Formulaire action={enregistrerProvision} libelle="Enregistrer la provision">
          <input type="hidden" name="date_arrete" value={arrete} />
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <label className="block">
              <span className="text-sm font-medium text-pop-encre">Agence</span>
              <select name="agence" required defaultValue="" className={champ}>
                <option value="" disabled>
                  Choisir une agence
                </option>
                {(parametres?.agences ?? []).map((a) => (
                  <option key={a} value={a}>
                    {a}
                  </option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="text-sm font-medium text-pop-encre">Montant (USD)</span>
              <input
                type="text"
                inputMode="decimal"
                name="montant"
                required
                placeholder="232632,94"
                className={`chiffres ${champ}`}
              />
            </label>
          </div>
          <label className="block">
            <span className="text-sm font-medium text-pop-encre">
              Note <span className="font-normal text-pop-gris">(base de la decision)</span>
            </span>
            <input
              type="text"
              name="note"
              placeholder="16 % — 1 % cumule/mois depuis fermeture, valide DAF"
              className={champ}
            />
          </label>
          <p className="text-[11px] leading-relaxed text-pop-gris">
            Arrete concerne&nbsp;: {dateLongue(arrete)}. Pour un autre arrete, changer la date
            en haut de page — une provision est attachee a UN arrete.
          </p>
        </Formulaire>
      </Section>

      {/* ── 3. REINTEGRATIONS FISCALES ──────────────────────────────────── */}
      <Section
        titre="Reintegrations fiscales (§67)"
        pourquoi={
          "IBP = (resultat comptable + reintegrations) × taux, a l'arrete annuel. La grille " +
          "vient du DAF : deux natures sont amorcees, elle reste a completer. Tant qu'elle " +
          "est incomplete, l'impot n'est pas deduit et le resultat « net » du 31/12 est en " +
          "realite un resultat AVANT impot."
        }
      >
        {parametres && parametres.reintegrations.length > 0 ? (
          <ul className="mb-4 divide-y divide-pop-bord rounded-lg border border-pop-bord">
            {parametres.reintegrations.map((r) => (
              <li
                key={r.compte_ou_ligne}
                className="flex flex-wrap items-center justify-between gap-3 px-3 py-2.5"
              >
                <div>
                  <p className="text-[13px] text-pop-encre">{r.compte_ou_ligne}</p>
                  <p className="text-[11px] text-pop-gris">
                    A effet du {dateLongue(r.date_effet)}
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  <span className="chiffres text-[13px] font-medium text-pop-encre">
                    {pourcent(fractionVersPourcent(r.taux_reintegration))}
                  </span>
                  <Formulaire action={supprimerReintegration} libelle="Retirer" discret enLigne>
                    <input type="hidden" name="compte_ou_ligne" value={r.compte_ou_ligne} />
                  </Formulaire>
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <p className="mb-4 text-[13px] text-pop-gris">Aucune reintegration enregistree.</p>
        )}

        <Formulaire action={enregistrerReintegration} libelle="Enregistrer la reintegration">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <label className="block sm:col-span-2">
              <span className="text-sm font-medium text-pop-encre">Nature de charge</span>
              <input
                type="text"
                name="compte_ou_ligne"
                required
                placeholder="communication"
                className={champ}
              />
            </label>
            <label className="block">
              <span className="text-sm font-medium text-pop-encre">Taux reintegre (%)</span>
              <input
                type="number"
                name="taux_pourcent"
                required
                min={0}
                max={100}
                step="any"
                placeholder="50"
                className={`chiffres ${champ}`}
              />
            </label>
          </div>
          <label className="block sm:max-w-xs">
            <span className="text-sm font-medium text-pop-encre">Date d&apos;effet</span>
            <input type="date" name="date_effet" required className={champ} />
          </label>
          <p className="text-[11px] leading-relaxed text-pop-gris">
            Saisir en pourcentage (50 pour 50 %). La valeur est stockee en fraction ; l&apos;API
            refuse tout ce qui sort de [0 ; 100] %, ce qui rend impossible d&apos;enregistrer
            « 50 » pour 5 000 % et de multiplier l&apos;IBP par cent.
          </p>
        </Formulaire>
      </Section>

      {/* ── 4. MAPPING BUDGETAIRE ───────────────────────────────────────── */}
      <Section
        titre="Mapping budgetaire : compte comptable → ligne budgetaire"
        pourquoi={
          "Source : le fichier de SUIVI BUDGETAIRE, feuilles « Resultat charges » et " +
          "« Resultat produits » (import en un passage depuis la page Import). Sans ce " +
          "mapping, aucun compte de la balance n'est rattache a une ligne : le realise du " +
          "suivi budgetaire vaut 0,00 partout, face a un budget pourtant charge."
        }
      >
        {mapping === null ? (
          <p className="mb-4 text-[13px] text-pop-danger">Mapping illisible pour le moment.</p>
        ) : (
          <p
            className={
              "mb-4 rounded-lg px-3 py-2 text-[13px] " +
              (mapping.nb_comptes > 0
                ? "bg-pop-ok/10 text-pop-ok"
                : "bg-pop-danger/10 text-pop-danger")
            }
          >
            {mapping.nb_comptes > 0 ? (
              <>
                {entier(mapping.nb_comptes)} comptes rattaches —{" "}
                {entier(mapping.nb_charges)} en charges, {entier(mapping.nb_produits)} en
                produits.
              </>
            ) : (
              <>
                Aucun compte rattache : le suivi budgetaire ne peut afficher aucun realise.
              </>
            )}
          </p>
        )}

        <Formulaire action={enregistrerMapping} libelle="Rattacher le compte">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-4">
            <label className="block">
              <span className="text-sm font-medium text-pop-encre">Compte</span>
              <input
                type="text"
                name="numero_compte"
                required
                placeholder="6.0.2.0.1"
                className={`chiffres ${champ}`}
              />
            </label>
            <label className="block sm:col-span-2">
              <span className="text-sm font-medium text-pop-encre">Ligne budgetaire</span>
              <input
                type="text"
                name="ligne_budgetaire"
                required
                placeholder="Frais de personnel"
                className={champ}
              />
            </label>
            <label className="block">
              <span className="text-sm font-medium text-pop-encre">Sens</span>
              <select name="sens" required defaultValue="charge" className={champ}>
                <option value="charge">Charge</option>
                <option value="produit">Produit</option>
              </select>
            </label>
          </div>
          <label className="block sm:max-w-xs">
            <span className="text-sm font-medium text-pop-encre">
              Date d&apos;effet <span className="font-normal text-pop-gris">(facultatif)</span>
            </span>
            <input type="date" name="date_effet" className={champ} />
            <span className="mt-1 block text-[11px] text-pop-gris">
              Vide = aujourd&apos;hui. La derniere date d&apos;effet l&apos;emporte.
            </span>
          </label>
        </Formulaire>

        {mapping !== null && mapping.lignes.length > 0 && (
          <details className="mt-4">
            <summary className="cursor-pointer text-[13px] font-medium text-pop-bleu-2">
              Voir et modifier les {entier(mapping.nb_comptes)} affectations en vigueur
            </summary>
            <div className="mt-2">
              <ExportSections
                titre="Mapping compte - ligne budgetaire"
                nom="PopPilot_mapping_budget"
                sections={[{
                  colonnes: [
                    { libelle: "Compte", cle: "numero_compte" },
                    { libelle: "Ligne budgetaire", cle: "ligne_budgetaire" },
                    { libelle: "Sens", cle: "sens" },
                  ],
                  lignes: mapping.lignes,
                }]}
              />
            </div>
            <div className="mt-2 max-h-96 overflow-y-auto rounded-lg border border-pop-bord">
              <table className="w-full border-collapse">
                <thead className="sticky top-0 bg-pop-fond">
                  <tr>
                    <th className="px-3 py-2 text-left text-[11px] font-semibold uppercase text-pop-gris">
                      Compte
                    </th>
                    <th className="px-3 py-2 text-left text-[11px] font-semibold uppercase text-pop-gris">
                      Ligne budgetaire
                    </th>
                    <th className="px-3 py-2 text-left text-[11px] font-semibold uppercase text-pop-gris">
                      Sens
                    </th>
                    <th className="px-3 py-2" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-pop-bord">
                  {mapping.lignes.map((l) => (
                    <tr key={l.numero_compte} className="hover:bg-pop-fond">
                      <td className="chiffres px-3 py-1.5 text-[12px] text-pop-encre">
                        {l.numero_compte}
                      </td>
                      <td className="px-3 py-1.5 text-[12px] text-pop-encre">
                        {l.ligne_budgetaire}
                      </td>
                      <td className="px-3 py-1.5 text-[12px] text-pop-gris">{l.sens}</td>
                      <td className="px-3 py-1.5 text-right">
                        <Formulaire action={supprimerMapping} libelle="Detacher" discret enLigne>
                          <input type="hidden" name="numero_compte" value={l.numero_compte} />
                        </Formulaire>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
        )}
      </Section>

      {/* ── 5. AGENCES ──────────────────────────────────────────────────── */}
      <Section
        titre="Referentiel des agences"
        pourquoi={
          "Ouvrir, fermer, suspendre, rouvrir. Une agence FERMEE garde un portefeuille reel " +
          "et declarable a la BCC, mais n'a plus d'agents : son encours n'est jamais classe " +
          "« orphelin » ni evalue en performance d'agents. Fermer une agence n'efface ni son " +
          "nom, ni sa region, ni sa date d'ouverture."
        }
      >
        {agences.length > 0 && (
          <ul className="mb-5 divide-y divide-pop-bord rounded-lg border border-pop-bord">
            {agences.map((a) => (
              <li key={a.code_agence} className="px-3 py-2.5">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="text-[13px] font-medium text-pop-encre">{a.code_agence}</p>
                  <span
                    className={
                      "rounded-full px-2.5 py-0.5 text-[11px] font-medium " +
                      (a.statut === "ACTIVE"
                        ? "bg-pop-ok/10 text-pop-ok"
                        : a.statut === "FERMEE"
                          ? "bg-pop-danger/10 text-pop-danger"
                          : "bg-pop-alerte/10 text-pop-alerte")
                    }
                  >
                    {LIBELLES_STATUT[a.statut] ?? a.statut}
                  </span>
                </div>
                <p className="mt-0.5 text-[11px] text-pop-gris">
                  {a.region ? `${a.region} · ` : ""}
                  {a.date_fermeture
                    ? `Fermee le ${dateLongue(a.date_fermeture)}${a.motif ? ` — ${a.motif}` : ""}`
                    : EFFET_STATUT[a.statut]}
                </p>
              </li>
            ))}
          </ul>
        )}

        <Formulaire action={enregistrerAgence} libelle="Enregistrer l'agence">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <label className="block">
              <span className="text-sm font-medium text-pop-encre">Code agence</span>
              <input
                type="text"
                name="code_agence"
                required
                list="agences-connues"
                placeholder="AGENCE DE GOMA"
                className={champ}
              />
              <datalist id="agences-connues">
                {agences.map((a) => (
                  <option key={a.code_agence} value={a.code_agence} />
                ))}
              </datalist>
              <span className="mt-1 block text-[11px] text-pop-gris">
                Un code inconnu CREE l&apos;agence ; un code existant la modifie.
              </span>
            </label>
            <label className="block">
              <span className="text-sm font-medium text-pop-encre">Statut</span>
              <select name="statut" required defaultValue="ACTIVE" className={champ}>
                {STATUTS_AGENCE.map((s) => (
                  <option key={s} value={s}>
                    {LIBELLES_STATUT[s]}
                  </option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="text-sm font-medium text-pop-encre">
                Date de fermeture{" "}
                <span className="font-normal text-pop-gris">(exigee si fermee)</span>
              </span>
              <input type="date" name="date_fermeture" className={champ} />
            </label>
            <label className="block">
              <span className="text-sm font-medium text-pop-encre">
                Motif <span className="font-normal text-pop-gris">(si fermee ou suspendue)</span>
              </span>
              <input
                type="text"
                name="motif"
                placeholder="Occupation M23 — agence non fonctionnelle"
                className={champ}
              />
            </label>
          </div>
          <p className="text-[11px] leading-relaxed text-pop-gris">
            Remettre une agence en ACTIVE efface sa date de fermeture et son motif : sinon
            elle trainerait indefiniment la trace d&apos;une fermeture revolue. Seuls les
            champs renseignes sont modifies.
          </p>
        </Formulaire>
      </Section>
    </div>
  );
}
