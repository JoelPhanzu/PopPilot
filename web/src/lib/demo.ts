/**
 * PopPilot — mode demonstration.
 *
 * A quoi ca sert : pouvoir ouvrir l'interface et VERIFIER LE CLOISONNEMENT PAR
 * ROLE avant que Supabase et l'API ne soient branches. Rien ici n'est un
 * chiffre officiel : ce sont des donnees d'illustration, calees sur les ordres
 * de grandeur de mai 2026 documentes dans CLAUDE.md (PAR1 1 188 447 = 10,99 % ;
 * provisions 938 244,42 ; 7 984 credits) pour que l'ecran ressemble au reel.
 *
 * Toute vue alimentee par ces donnees porte un bandeau « donnees de
 * demonstration » : un chiffre non issu du socle ne doit jamais pouvoir passer
 * pour un chiffre du socle.
 */
import type { Profil, Role } from "@/lib/roles";
import type { ReponsePar, LigneAgence, ReponseProvisions } from "@/lib/credit";
import type {
  EtatsFinanciers,
  Indicateur,
  Indicateurs,
  Rubriques,
} from "@/lib/comptabilite";

/** Cookie du mode demonstration (aucune valeur secrete : un simple role). */
export const COOKIE_DEMO = "pp_demo_role";

/** Arrete de reference des donnees d'illustration. */
export const ARRETE_DEMO = "2026-05-30";

export function profilDemo(role: Role): Profil {
  return {
    login: `demo_${role.toLowerCase()}`,
    role,
    agence: role === "AGENCE" ? "VICTOIRE" : null,
    demo: true,
  };
}

/**
 * Lignes par agence. Les totaux globaux sont RECALCULES par somme (voir
 * `parDemo`) : impossible qu'un total affiche ne corresponde pas au detail.
 *
 * Les NOMS D'AGENCE sont les vrais : a Kinshasa, VICTOIRE, OZONE, MASINA et
 * GOMBE — pas d'agence inventee, meme en demonstration. Un nom fictif finit
 * toujours par etre lu comme reel sur une capture d'ecran, et il ne
 * correspondrait a aucun compte de test (le role AGENCE demo est rattache a
 * VICTOIRE, comme le compte `bmvictoire`). Seuls les MONTANTS sont des
 * illustrations. Le lien agence <-> montant n'a donc aucune valeur : ce sont
 * des ordres de grandeur repartis, pas les chiffres de ces agences.
 */
type AgenceDemo = Omit<LigneAgence, "pct_par30" | "par90"> & {
  par90: number;
  provisions: number;
  nb_credits: number;
  nb_clients: number;
};

const AGENCES_DEMO: AgenceDemo[] = [
  { agence: "GOMBE", encours: 3_412_560, par1: 331_018, par30: 288_402, par90: 214_330, provisions: 261_430.1, nb_credits: 2510, nb_clients: 2395, statut: "ACTIVE" },
  { agence: "VICTOIRE", encours: 2_156_890, par1: 214_776, par30: 190_120, par90: 141_664, provisions: 169_880.45, nb_credits: 1584, nb_clients: 1509, statut: "ACTIVE" },
  { agence: "LUBUMBASHI", encours: 1_874_320, par1: 196_330, par30: 172_118, par90: 130_442, provisions: 155_214.3, nb_credits: 1376, nb_clients: 1312, statut: "ACTIVE" },
  { agence: "MATADI", encours: 1_208_440, par1: 129_006, par30: 113_220, par90: 86_118, provisions: 101_442.88, nb_credits: 887, nb_clients: 846, statut: "ACTIVE" },
  { agence: "KIKWIT", encours: 712_684, par1: 76_317, par30: 67_140, par90: 51_446, provisions: 60_276.69, nb_credits: 523, nb_clients: 499, statut: "ACTIVE" },
  // Goma : agence FERMEE (occupation M23). Portefeuille gele mais REEL — il
  // reste dans l'encours, le PAR et les provisions (CLAUDE.md). Seule la
  // detection d'orphelins l'exclut.
  { agence: "GOMA", encours: 1_449_000, par1: 241_000, par30: 221_000, par90: 188_000, provisions: 190_000, nb_credits: 1104, nb_clients: 1051, statut: "FERMEE" },
];

/** Colonnes numeriques sommables (le statut, lui, ne s'additionne pas). */
type CleChiffree =
  | "encours" | "par1" | "par30" | "par90"
  | "provisions" | "nb_credits" | "nb_clients";

function somme(cle: CleChiffree): number {
  return AGENCES_DEMO.reduce((total, a) => total + a[cle], 0);
}

/** Reponse /par de demonstration, dans le format EXACT de l'API. */
export function parDemo(arrete: string, role: Role): ReponsePar {
  const encours = somme("encours");
  const par1 = somme("par1");
  const par30 = somme("par30");
  const par90 = somme("par90");

  return {
    arrete,
    role,
    global: {
      encours,
      par1,
      par30,
      par90,
      pct_par1: (par1 / encours) * 100,
      pct_par30: (par30 / encours) * 100,
      pct_par90: (par90 / encours) * 100,
      nb_credits: somme("nb_credits"),
      nb_clients: somme("nb_clients"),
    },
    agences: AGENCES_DEMO.map((a) => ({
      agence: a.agence,
      encours: a.encours,
      par1: a.par1,
      par30: a.par30,
      par90: a.par90,
      pct_par30: (a.par30 / a.encours) * 100,
      statut: a.statut,
    })),
  };
}

/** Provisions de demonstration, dans le format EXACT de deriver_provisions. */
export function provisionsDemo(): ReponseProvisions {
  return {
    provision_capital_totale: somme("provisions"),
    par_agence: Object.fromEntries(AGENCES_DEMO.map((a) => [a.agence, a.provisions])),
  };
}

/* ==========================================================================
   COMPTABILITE & INDICATEURS — donnees d'illustration
   ==========================================================================

   Memes regles que pour le credit : ce ne sont PAS des chiffres officiels,
   mais ils sont CALES sur les ordres de grandeur reellement valides et
   documentes dans CLAUDE.md (juillet 2026) — total actif 12 592 520,01 ;
   resultat net 142 477,78 ; fonds propres de base 4 555 098 ; portefeuille
   brut 10 974 953,62 ; PAR1 bilan 1 348 331 ; depots a vue 1 837 270 ;
   liquidite E4 75,61 %. Un ecran de demonstration qui ressemble au reel se
   critique comme le reel ; un ecran peuple de nombres ronds ne se critique
   pas du tout.

   Deux contraintes que ces valeurs respectent, et qui ne sont pas decoratives :
     - le bilan BOUCLE (actif = passif, resultat inclus) ;
     - chaque ratio est le VRAI quotient de son numerateur par son
       denominateur, tous deux presents dans les agregats. Un ratio pose a la
       main serait invisible a l'oeil mais rendrait l'ecran incoherent des
       qu'on le decompose — et on le decompose, c'est meme le but des colonnes
       numerateur / denominateur.
   ========================================================================== */

/** Taux de reference des montants CDF derives (documente §43). */
const TAUX_DEMO = 2268.75;

const TOTAL_ACTIF_DEMO = 12_592_520.01;
const RESULTAT_DEMO = 142_477.78;
const PRODUITS_DEMO = 862_477.78;
const CHARGES_DEMO = 720_000.0;

const PORTEFEUILLE_BRUT_DEMO = 10_974_953.62; // comptes 31+32+39
const PAR1_DEMO = 1_348_331.0; // = compte 39 (invariant X-1)
const PAR30_DEMO = 1_186_392.49;
const IMMOB_NETTES_DEMO = 1_007_401.6;
const DISPONIBLES_DEMO = 1_389_168.0; // comptes 56+57
const DEPOTS_A_VUE_DEMO = 1_837_270.0; // epargne a vue (source inventaire)
const FP_BASE_DEMO = 4_555_098.0; // comptes 10-14, resultat NON affecte
const FP_PRUDENTIELS_DEMO = 4_802_771.0; // base + compte 18

// Moyennes de periode (arrete + 31/12 precedent) / 2 — disponibles en demo.
const PORTEFEUILLE_MOYEN_DEMO = 10_600_000.0;
const FP_MOYENS_DEMO = 4_390_000.0;
const ACTIF_MOYEN_DEMO = 12_100_000.0;

const CHARGES_PERSONNEL_DEMO = 258_400.0; // compte 66
const INTERETS_PRODUITS_DEMO = 795_320.0; // comptes 70-72
const NB_EMPRUNTEURS_DEMO = 8_121;
const NB_AGENTS_DEMO = 39;

/** Etats financiers de demonstration, dans le format EXACT du moteur. */
export function etatsDemo(): EtatsFinanciers {
  // Rubriques du mapping §40 (engine/etats_financiers.py), pas des libelles
  // inventes : l'ecran doit montrer les lignes que la balance produit.
  const actif: Rubriques = {
    "Opérations clientèle": 10_036_709.2,
    "Trésorerie": DISPONIBLES_DEMO,
    "Immobilisations": IMMOB_NETTES_DEMO,
    "Opérations diverses": 159_241.21,
  };
  const passif: Rubriques = {
    "Opérations clientèle": 6_406_264.0, // depots 33+34 (≈ epargne inventaire)
    "Fonds propres": FP_BASE_DEMO,
    "Opérations diverses": 1_488_680.23,
  };

  const totalActif = Object.values(actif).reduce((s, v) => s + v, 0);
  // Le resultat de l'exercice vient EQUILIBRER le passif : il n'est pas une
  // rubrique de la balance, il s'y ajoute (meme regle que le moteur).
  const totalPassif =
    Object.values(passif).reduce((s, v) => s + v, 0) + RESULTAT_DEMO;

  return {
    taux_change: TAUX_DEMO,
    actif,
    passif,
    total_actif: totalActif,
    total_passif: totalPassif,
    produits: PRODUITS_DEMO,
    charges: CHARGES_DEMO,
    resultat_net: RESULTAT_DEMO,
    resultat_comptable: RESULTAT_DEMO,
    resultat_net_cdf: RESULTAT_DEMO * TAUX_DEMO,
    controles: {
      bilan_equilibre_ecart: totalActif - totalPassif,
      resultat_net: RESULTAT_DEMO,
      resultat_comptable: RESULTAT_DEMO,
      // En cours d'annee l'IBP n'est pas du : comptable = net (§67).
      ibp_deduit: false,
      ibp_du_a_cet_arrete: false,
      comptes_non_mappes: 0,
      fonds_propres: FP_BASE_DEMO + RESULTAT_DEMO,
      taux_absent: null,
    },
    comptes_non_mappes: [],
    par_prefixe: {},
  };
}

/** Un indicateur dont la valeur est le VRAI quotient de ses deux termes. */
function ratio(
  num: number,
  den: number,
  norme: string,
  extra: Partial<Indicateur> = {},
): Indicateur {
  return {
    valeur: den === 0 ? null : (num / den) * 100,
    num,
    den,
    norme,
    ...extra,
  };
}

/** Indicateurs prudentiels de demonstration, dans le format EXACT du moteur. */
export function indicateursDemo(arrete: string): Indicateurs {
  const indicateurs: Record<string, Indicateur> = {
    A1_PAR30: ratio(PAR30_DEMO, PORTEFEUILLE_BRUT_DEMO, "< 5 %", {
      source: "crédit Phase 1",
    }),
    A1bis_PAR1: ratio(PAR1_DEMO, PORTEFEUILLE_BRUT_DEMO, "(risque global)", {
      source: "crédit Phase 1",
    }),
    // A2 et E6 restent NON CALCULES, comme dans le moteur : c'est precisement
    // ce que l'ecran doit savoir afficher sans les compter pour conformes.
    A2_abandon: {
      valeur: null,
      num: null,
      den: null,
      norme: "< 2 %",
      motif:
        "radiations (≥361 j au 31/12) non encore calculées — mode clôture annuelle à construire",
    },
    B1_efficacite: ratio(CHARGES_PERSONNEL_DEMO, PORTEFEUILLE_MOYEN_DEMO, "13-21 %"),
    B2_emprunteurs_agent: {
      valeur: NB_EMPRUNTEURS_DEMO / NB_AGENTS_DEMO,
      num: NB_EMPRUNTEURS_DEMO,
      den: NB_AGENTS_DEMO,
      norme: "> 130",
      sans_pourcent: true,
    },
    C1_ROE: ratio(RESULTAT_DEMO, FP_MOYENS_DEMO, "> 15 %"),
    C2_ROA: ratio(RESULTAT_DEMO, ACTIF_MOYEN_DEMO, "> 3 %"),
    C3_rendement: ratio(INTERETS_PRODUITS_DEMO, PORTEFEUILLE_MOYEN_DEMO, "> 15 %"),
    C4_autosuffisance: ratio(PRODUITS_DEMO, CHARGES_DEMO, "> 119,2 %"),
    D1_encaisse_oisive: ratio(DISPONIBLES_DEMO, TOTAL_ACTIF_DEMO, "< 20 %"),
    D2_taux_encours: ratio(PORTEFEUILLE_BRUT_DEMO, TOTAL_ACTIF_DEMO, "> 70 %"),
    D3_immobilisations: ratio(IMMOB_NETTES_DEMO, TOTAL_ACTIF_DEMO, "< 10 %"),
    E1_capital_min: ratio(FP_BASE_DEMO, 700_000, "≥ 100 %"),
    E2_solvabilite: ratio(FP_PRUDENTIELS_DEMO, TOTAL_ACTIF_DEMO, "≥ 10 %"),
    E3_capitalisation: ratio(FP_BASE_DEMO, TOTAL_ACTIF_DEMO, "≥ 15 %"),
    E4_liquidite: ratio(DISPONIBLES_DEMO, DEPOTS_A_VUE_DEMO, "≥ 20 %", {
      source: "dispo bilan ÷ dépôts à vue épargne",
    }),
    E5_couverture_immob: ratio(IMMOB_NETTES_DEMO, FP_PRUDENTIELS_DEMO, "≤ 50 %"),
    E6_couverture_emplois_MLT: {
      valeur: null,
      num: null,
      den: null,
      norme: "≥ 100 %",
      motif:
        "ressources et emplois > 1 an non distingués (crédit MLT / DAT) — à affiner",
    },
  };

  return {
    date_arrete: arrete,
    par_credit: { date_credit: arrete, meme_mois: true },
    moyennes_de_periode: true,
    date_debut_exercice: `${Number(arrete.slice(0, 4)) - 1}-12-31`,
    // Reserve reelle, documentee dans CLAUDE.md : le nombre d'agents du ratio
    // B2 doit venir du rapport RH, pas du fichier OBJECTIF.
    avertissements: {
      B2_emprunteurs_agent:
        "Nombre d'agents issu du roster OBJECTIF (39) ; le rapport RH officiel en compte 29. " +
        "Le ratio réglementaire doit s'appuyer sur l'effectif RH.",
    },
    agregats: {
      nb_agents_roster: NB_AGENTS_DEMO,
      nb_emprunteurs: NB_EMPRUNTEURS_DEMO,
      portefeuille_brut: PORTEFEUILLE_BRUT_DEMO,
      PAR1_credit: PAR1_DEMO,
      PAR30_credit: PAR30_DEMO,
      capital_retard_bilan_39: PAR1_DEMO,
      immob_nettes: IMMOB_NETTES_DEMO,
      depots_cautionnements_27: 47_320.0,
      disponibles_56_57: DISPONIBLES_DEMO,
      depots_a_vue_epargne: DEPOTS_A_VUE_DEMO,
      total_actif: TOTAL_ACTIF_DEMO,
      fonds_propres_base: FP_BASE_DEMO,
      fonds_propres_prudentiels: FP_PRUDENTIELS_DEMO,
      fonds_propres_base_avec_resultat: FP_BASE_DEMO + RESULTAT_DEMO,
      fonds_propres_prudentiels_avec_resultat: FP_PRUDENTIELS_DEMO + RESULTAT_DEMO,
      resultat: RESULTAT_DEMO,
      produits: PRODUITS_DEMO,
      charges: CHARGES_DEMO,
    },
    indicateurs,
  };
}
