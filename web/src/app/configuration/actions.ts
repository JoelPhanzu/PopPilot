"use server";

/**
 * PopPilot — actions serveur de la page Configuration.
 *
 * Elles ne font que TRANSMETTRE a l'API, qui valide et ecrit. Aucune regle
 * metier ici : le controle du taux (> 0), de la fraction de reintegration
 * (entre 0 et 1), de la date de fermeture obligatoire appartient a
 * `api/configuration.py`, seul endroit ou il vaut pour TOUS les appelants.
 * Le dupliquer cote front ferait croire que le front protege, alors qu'il ne
 * fait que ne pas reclamer.
 *
 * Le controle de role est refait ici par PRUDENCE, pas par necessite : l'API
 * refuse deja tout appelant hors DIRECTION / CDG.
 *
 * Ce module etant en « use server », chacun de ses exports devient une action
 * appelable depuis le navigateur — d'ou l'absence stricte de toute constante
 * exportee (elles vivent dans `@/lib/configuration`).
 */
import { revalidatePath } from "next/cache";
import { sessionCourante } from "@/lib/session";
import { peutEcrire } from "@/lib/roles";
import { appelerApiEcriture } from "@/lib/api";
import type { EtatConfiguration } from "@/lib/configuration";

/** Chemins dont les chiffres dependent d'un parametre saisi ici. */
function rafraichir() {
  // Un taux, une provision ou un mapping qui change modifie ce que les autres
  // ecrans affichent : les laisser servir leur version d'avant la saisie
  // donnerait a croire que la saisie n'a pas pris.
  for (const chemin of ["/configuration", "/comptabilite", "/budget", "/credit", "/epargne"]) {
    revalidatePath(chemin);
  }
}

async function executer(
  methode: "POST" | "DELETE",
  chemin: string,
  corps: unknown,
  succes: string,
): Promise<EtatConfiguration> {
  const { profil, jeton } = await sessionCourante();

  if (!peutEcrire(profil)) {
    return { etat: "echec", message: "Configuration reservee aux roles Direction et Controle de gestion." };
  }
  if (profil?.demo) {
    return {
      etat: "echec",
      message:
        "Mode demonstration : il n'y a pas de base a parametrer. Renseigner web/.env.local " +
        "et api/.env, puis se connecter avec un vrai compte.",
    };
  }

  const reponse = await appelerApiEcriture(methode, chemin, corps, jeton);
  if (!reponse.ok) return { etat: "echec", message: reponse.erreur };

  rafraichir();
  return { etat: "succes", message: succes };
}

function texte(donnees: FormData, champ: string): string {
  const valeur = donnees.get(champ);
  return typeof valeur === "string" ? valeur.trim() : "";
}

/* ── Taux de change USD → CDF ─────────────────────────────────────────────── */
export async function enregistrerTaux(
  _precedent: EtatConfiguration,
  donnees: FormData,
): Promise<EtatConfiguration> {
  const date_effet = texte(donnees, "date_effet");
  const taux = texte(donnees, "taux").replace(",", ".");
  return executer("POST", "/configuration/taux", { date_effet, taux },
    `Taux ${taux} CDF/USD enregistre a effet du ${date_effet}.`);
}

/* ── Provision manuelle par agence (decision DAF) ─────────────────────────── */
export async function enregistrerProvision(
  _precedent: EtatConfiguration,
  donnees: FormData,
): Promise<EtatConfiguration> {
  const agence = texte(donnees, "agence");
  const date_arrete = texte(donnees, "date_arrete");
  return executer("POST", "/configuration/provision-manuelle", {
    date_arrete,
    agence,
    montant: texte(donnees, "montant").replace(",", "."),
    note: texte(donnees, "note"),
  }, `Provision manuelle enregistree pour ${agence} au ${date_arrete}. ` +
     "Le bareme automatique ne s'applique plus a cette agence pour cet arrete.");
}

export async function supprimerProvision(
  _precedent: EtatConfiguration,
  donnees: FormData,
): Promise<EtatConfiguration> {
  const agence = texte(donnees, "agence");
  const arrete = texte(donnees, "date_arrete");
  const chemin =
    `/configuration/provision-manuelle?arrete=${encodeURIComponent(arrete)}` +
    `&agence=${encodeURIComponent(agence)}`;
  return executer("DELETE", chemin, null,
    `Provision manuelle de ${agence} retiree : le bareme automatique reprend.`);
}

/* ── Reintegrations fiscales (§67) ────────────────────────────────────────── */
export async function enregistrerReintegration(
  _precedent: EtatConfiguration,
  donnees: FormData,
): Promise<EtatConfiguration> {
  const nature = texte(donnees, "compte_ou_ligne");
  // Saisi en POURCENT a l'ecran (c'est ainsi qu'en parle le DAF), stocke en
  // FRACTION : l'API refuse toute valeur hors [0 ; 1], ce qui rend impossible
  // d'enregistrer « 50 » pour 50 % — une erreur qui multiplierait l'IBP par 100.
  const pourcent = Number(texte(donnees, "taux_pourcent").replace(",", "."));
  if (!Number.isFinite(pourcent)) {
    return { etat: "echec", message: "Taux de reintegration illisible." };
  }
  return executer("POST", "/configuration/reintegration", {
    date_effet: texte(donnees, "date_effet"),
    compte_ou_ligne: nature,
    taux_reintegration: pourcent / 100,
  }, `Reintegration « ${nature} » enregistree a ${pourcent} %.`);
}

export async function supprimerReintegration(
  _precedent: EtatConfiguration,
  donnees: FormData,
): Promise<EtatConfiguration> {
  const nature = texte(donnees, "compte_ou_ligne");
  return executer(
    "DELETE",
    `/configuration/reintegration?compte_ou_ligne=${encodeURIComponent(nature)}`,
    null,
    `Reintegration « ${nature} » retiree.`,
  );
}

/* ── Mapping budgetaire compte → ligne ────────────────────────────────────── */
export async function enregistrerMapping(
  _precedent: EtatConfiguration,
  donnees: FormData,
): Promise<EtatConfiguration> {
  const compte = texte(donnees, "numero_compte");
  const ligne = texte(donnees, "ligne_budgetaire");
  const corps: Record<string, string> = {
    numero_compte: compte,
    ligne_budgetaire: ligne,
    sens: texte(donnees, "sens"),
  };
  const date_effet = texte(donnees, "date_effet");
  if (date_effet) corps.date_effet = date_effet;
  return executer("POST", "/configuration/mapping-budget", corps,
    `Compte ${compte} rattache a « ${ligne} ».`);
}

export async function supprimerMapping(
  _precedent: EtatConfiguration,
  donnees: FormData,
): Promise<EtatConfiguration> {
  const compte = texte(donnees, "numero_compte");
  return executer(
    "DELETE",
    `/configuration/mapping-budget?numero_compte=${encodeURIComponent(compte)}`,
    null,
    `Compte ${compte} detache de sa ligne budgetaire.`,
  );
}

/* ── Agences : ouvrir, fermer, suspendre, rouvrir ─────────────────────────── */
export async function enregistrerAgence(
  _precedent: EtatConfiguration,
  donnees: FormData,
): Promise<EtatConfiguration> {
  const code = texte(donnees, "code_agence");
  const statut = texte(donnees, "statut");

  const corps: Record<string, string | null> = { code_agence: code };
  for (const champ of ["nom", "region", "motif", "date_ouverture", "date_fermeture"]) {
    const valeur = texte(donnees, champ);
    // Un champ vide vaut « efface-le » cote API, ce qui permet de ROUVRIR une
    // agence (date_fermeture remise a vide). Le champ absent, lui, ne touche a
    // rien — d'ou l'envoi explicite de null plutot que l'omission.
    if (donnees.has(champ)) corps[champ] = valeur || null;
  }
  if (statut) corps.statut = statut;

  const effet =
    statut === "FERMEE"
      ? " Son portefeuille reste declarable, mais n'est plus evalue en performance d'agents."
      : statut === "ACTIVE"
        ? " Date de fermeture et motif effaces."
        : "";
  return executer("POST", "/agences", corps, `Agence ${code} enregistree (${statut || "inchangee"}).${effet}`);
}
