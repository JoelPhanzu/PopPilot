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

/** Cookie du mode demonstration (aucune valeur secrete : un simple role). */
export const COOKIE_DEMO = "pp_demo_role";

/** Arrete de reference des donnees d'illustration. */
export const ARRETE_DEMO = "2026-05-30";

export function profilDemo(role: Role): Profil {
  return {
    login: `demo_${role.toLowerCase()}`,
    role,
    agence: role === "AGENCE" ? "KINSHASA MATETE" : null,
    demo: true,
  };
}

/**
 * Lignes par agence. Les totaux globaux sont RECALCULES par somme (voir
 * `parDemo`) : impossible qu'un total affiche ne corresponde pas au detail.
 */
type AgenceDemo = Omit<LigneAgence, "pct_par30" | "par90"> & {
  par90: number;
  provisions: number;
  nb_credits: number;
  nb_clients: number;
};

const AGENCES_DEMO: AgenceDemo[] = [
  { agence: "KINSHASA CENTRE", encours: 3_412_560, par1: 331_018, par30: 288_402, par90: 214_330, provisions: 261_430.1, nb_credits: 2510, nb_clients: 2395, statut: "ACTIVE" },
  { agence: "KINSHASA MATETE", encours: 2_156_890, par1: 214_776, par30: 190_120, par90: 141_664, provisions: 169_880.45, nb_credits: 1584, nb_clients: 1509, statut: "ACTIVE" },
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
