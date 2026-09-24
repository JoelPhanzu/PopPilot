import "server-only";

/**
 * PopPilot — domaine CREDIT : types de l'API et chargement du tableau de bord.
 *
 * Aucun indicateur n'est recalcule ici. Le PAR, les provisions et l'encours
 * viennent des moteurs Python valides au centime contre les fichiers reels
 * (engine/par.py, engine/derivation.py) : le front AFFICHE, il ne calcule pas.
 * Le seul arithmetique tolere ici est l'agregation d'un total deja filtre
 * (cf. `restreindreAUneAgence`), et elle est explicite.
 */
import { appelerApi } from "@/lib/api";
import { parDemo, provisionsDemo } from "@/lib/demo";
import { aAccesTotal, filtrerParAgence, type Profil } from "@/lib/roles";

/** Une ligne « agence » telle que la renvoie GET /par. */
export type LigneAgence = {
  agence: string;
  encours: number;
  par1: number;
  par30: number;
  /** L'API ne renvoie pas le PAR90 par agence : optionnel, jamais invente. */
  par90?: number | null;
  pct_par30: number;
  /** Statut d'agence (ACTIVE / FERMEE / SUSPENDUE) quand il est connu. */
  statut?: string | null;
};

export type GlobalPar = {
  encours?: number;
  par1?: number;
  par30?: number;
  par90?: number;
  pct_par1?: number;
  pct_par30?: number;
  pct_par90?: number;
  nb_credits?: number;
  nb_clients?: number;
};

export type ReponsePar = {
  arrete: string;
  role: string;
  global: GlobalPar;
  agences: LigneAgence[];
};

export type ReponseProvisions = {
  provision_capital_totale: number;
  par_agence?: Record<string, number>;
  par_tranche?: Record<string, number>;
  provisions_manuelles?: Record<string, string>;
};

// Provenance des chiffres : type commun a tous les domaines (cf. lib/source.ts).
// Re-exporte ici pour ne rien casser des ecrans qui l'importaient du credit.
export type { SourceDonnees } from "@/lib/source";
import type { SourceDonnees } from "@/lib/source";

export type TableauCredit = {
  arrete: string;
  source: SourceDonnees;
  par: ReponsePar;
  provisions: ReponseProvisions | null;
  /** Pourquoi les provisions manquent (403 pour un role AGENCE, API muette…). */
  noteProvisions: string | null;
  /** Message a afficher quand l'API n'a pas repondu. */
  erreurApi: string | null;
};

/**
 * Recalcule le bloc « global » sur les seules agences visibles.
 *
 * POURQUOI : l'API fait deja ce travail pour /par, mais elle est la seule
 * source a le garantir. Si un jour un endpoint renvoyait un total institution
 * a un role AGENCE (l'erreur exacte corrigee sur /decaissements, cf. CLAUDE.md),
 * l'ecran ne le relaierait pas : cote front, le total d'un role AGENCE est
 * TOUJOURS la somme de ce qu'il a le droit de voir.
 */
function restreindreAUneAgence(lignes: LigneAgence[]): GlobalPar {
  const total = (cle: "encours" | "par1" | "par30") =>
    lignes.reduce((s, l) => s + (l[cle] ?? 0), 0);
  const encours = total("encours");
  const par1 = total("par1");
  const par30 = total("par30");
  const par90 = lignes.every((l) => typeof l.par90 === "number")
    ? lignes.reduce((s, l) => s + (l.par90 as number), 0)
    : undefined;

  return {
    encours,
    par1,
    par30,
    par90,
    pct_par1: encours ? (par1 / encours) * 100 : undefined,
    pct_par30: encours ? (par30 / encours) * 100 : undefined,
    pct_par90: encours && par90 !== undefined ? (par90 / encours) * 100 : undefined,
  };
}

/** Applique le cloisonnement a une reponse /par, quelle qu'en soit la source. */
function cloisonner(reponse: ReponsePar, profil: Profil): ReponsePar {
  const agences = filtrerParAgence(profil, reponse.agences, "agence");
  return {
    ...reponse,
    role: profil.role,
    agences,
    global: aAccesTotal(profil) ? reponse.global : restreindreAUneAgence(agences),
  };
}

/**
 * Charge le tableau de bord credit.
 *
 * Deux appels : GET /par?arrete=… (tous roles, cloisonne par l'API) et
 * GET /provisions?arrete=… (reserve aux roles a acces total cote API — on ne
 * le demande donc meme pas pour un role AGENCE : reclamer un 403 n'apprend
 * rien a personne).
 *
 * Si l'API ne repond pas et que le profil est un profil de demonstration, on
 * bascule sur les donnees d'illustration — signalees comme telles a l'ecran.
 */
export async function chargerTableauCredit(
  arrete: string,
  profil: Profil,
  jeton: string | null,
): Promise<TableauCredit> {
  const reponse = await appelerApi<ReponsePar>(
    `/par?arrete=${encodeURIComponent(arrete)}`,
    jeton,
  );

  if (!reponse.ok) {
    if (profil.demo) {
      return {
        arrete,
        source: "demonstration",
        par: cloisonner(parDemo(arrete, profil.role), profil),
        provisions: aAccesTotal(profil) ? provisionsDemo() : null,
        noteProvisions: aAccesTotal(profil)
          ? null
          : "Les provisions sont un agregat institution : reserve aux roles DIRECTION, CDG et AUDIT.",
        erreurApi: reponse.erreur,
      };
    }
    return {
      arrete,
      source: "api",
      par: { arrete, role: profil.role, global: {}, agences: [] },
      provisions: null,
      noteProvisions: null,
      erreurApi: reponse.erreur,
    };
  }

  let provisions: ReponseProvisions | null = null;
  let noteProvisions: string | null = null;

  if (aAccesTotal(profil)) {
    const p = await appelerApi<ReponseProvisions>(
      `/provisions?arrete=${encodeURIComponent(arrete)}`,
      jeton,
    );
    if (p.ok) provisions = p.donnees;
    else noteProvisions = p.erreur;
  } else {
    noteProvisions =
      "Les provisions sont un agregat institution : reserve aux roles DIRECTION, CDG et AUDIT.";
  }

  return {
    arrete,
    source: "api",
    par: cloisonner(reponse.donnees, profil),
    provisions,
    noteProvisions,
    erreurApi: null,
  };
}

/**
 * Arrete affiche quand l'URL n'en precise aucun.
 *
 * Il ne suit PAS `ARRETE_DEMO` : la date d'illustration du mode demonstration
 * et la date reellement chargee dans le socle sont deux choses differentes, et
 * les confondre faisait atterrir le tableau de bord sur un arrete absent — 404
 * « Aucun pret pour l'arrete » a chaque ouverture.
 *
 * Valeur calee sur ce que contient la base : l'extraction de mai 2026 y est
 * rangee au 2026-05-31 (7 984 prets). A corriger le jour ou un arrete plus
 * recent devient la reference.
 */
export const ARRETE_PAR_DEFAUT = "2026-05-31";

// ─────────────────────────────────────────────────────────────────────────────
// Tableau de bord FILTRE — GET /credit/filtre (api/filtres_credit.py).
//
// Additif : sans filtre, la page garde /par + /provisions. Des qu'un axe est
// choisi, les memes moteurs (PAR, bareme) tournent sur la selection de prets
// faite par engine/moteur_filtres AVANT calcul. Le front ne filtre rien.
// ─────────────────────────────────────────────────────────────────────────────

/** Axes de filtrage, tels qu'ils vivent dans l'URL. */
export type FiltresCredit = {
  agence?: string;
  sexe?: string;
  produits?: string[];
  duree?: string;
  client?: string;
  agent?: string;
  superviseur?: string;
};

export const CLES_FILTRES = [
  "agence",
  "sexe",
  "produits",
  "duree",
  "client",
  "agent",
  "superviseur",
] as const;

/** Valeurs des menus deroulants (GET /credit/filtres/valeurs), deja cloisonnees. */
export type ValeursFiltres = {
  agences: string[];
  agents: string[];
  superviseurs: string[];
  produits: string[];
  sexes: string[];
  durees: string[];
};

type ReponseFiltre = {
  arrete: string;
  role: string;
  portee: string;
  filtres: Record<string, unknown>;
  nb_prets_selectionnes: number;
  global: GlobalPar;
  provisions: {
    bareme: number;
    complement_manuel: number;
    total: number;
    complement_manuel_inclus: boolean;
    complements_exclus: string[];
  };
  agences: (LigneAgence & { provision: number })[];
};

export type TableauCreditFiltre = TableauCredit & {
  selection: { nb_prets: number; noteComplement: string | null } | null;
};

/** Lit les filtres de l'URL ; une valeur vide = pas de filtre. */
export function lireFiltres(
  sp: Record<string, string | string[] | undefined>,
): FiltresCredit {
  const un = (k: string) => {
    const v = sp[k];
    const s = Array.isArray(v) ? v[0] : v;
    return s && s.trim() ? s.trim() : undefined;
  };
  const brut = sp.produits;
  const produits = (Array.isArray(brut) ? brut : brut ? [brut] : []).filter((p) => p.trim());
  return {
    agence: un("agence"),
    sexe: un("sexe"),
    produits: produits.length ? produits : undefined,
    duree: un("duree"),
    client: un("client"),
    agent: un("agent"),
    superviseur: un("superviseur"),
  };
}

export function filtresActifs(f: FiltresCredit): boolean {
  return CLES_FILTRES.some((k) => (k === "produits" ? !!f.produits?.length : !!f[k]));
}

function requeteFiltres(arrete: string, f: FiltresCredit): string {
  const q = new URLSearchParams({ arrete });
  for (const k of CLES_FILTRES) {
    if (k === "produits") f.produits?.forEach((p) => q.append("produits", p));
    else if (f[k]) q.set(k, f[k] as string);
  }
  return q.toString();
}

/** Menus deroulants. null si l'API ne repond pas : on n'invente pas de liste. */
export async function chargerValeursFiltres(
  arrete: string,
  jeton: string | null,
): Promise<ValeursFiltres | null> {
  const r = await appelerApi<ValeursFiltres>(
    `/credit/filtres/valeurs?arrete=${encodeURIComponent(arrete)}`,
    jeton,
  );
  return r.ok ? r.donnees : null;
}

/**
 * Tableau de bord sur une selection de prets. Meme forme que
 * `chargerTableauCredit` : les cartes, le graphique et le tableau ne savent
 * pas qu'ils affichent une selection.
 *
 * Provisions : comme sur le chemin non filtre, elles ne sont montrees qu'aux
 * roles a acces total (l'API les calcule pour tous ; l'ecran reste aligne sur
 * la regle de /provisions).
 */
export async function chargerTableauCreditFiltre(
  arrete: string,
  filtres: FiltresCredit,
  profil: Profil,
  jeton: string | null,
): Promise<TableauCreditFiltre> {
  const r = await appelerApi<ReponseFiltre>(
    `/credit/filtre?${requeteFiltres(arrete, filtres)}`,
    jeton,
  );

  if (!r.ok) {
    return {
      arrete,
      source: "api",
      par: { arrete, role: profil.role, global: {}, agences: [] },
      provisions: null,
      noteProvisions: null,
      erreurApi: profil.demo
        ? `Les filtres interrogent les moteurs : indisponibles en mode demonstration. (${r.erreur})`
        : r.erreur,
      selection: null,
    };
  }

  const d = r.donnees;
  const total = aAccesTotal(profil);
  const p = d.provisions;
  const noteComplement = p.complements_exclus.length
    ? `Complement manuel DAF (${p.complements_exclus.join(", ")}) exclu : il est saisi par agence ` +
      "et ne se repartit ni par sexe, ni par produit, ni par agent."
    : null;

  return {
    arrete,
    source: "api",
    par: cloisonner(
      { arrete: d.arrete, role: d.role, global: d.global, agences: d.agences },
      profil,
    ),
    provisions: total
      ? {
          provision_capital_totale: p.total,
          par_agence: Object.fromEntries(d.agences.map((a) => [a.agence, a.provision])),
        }
      : null,
    noteProvisions: total
      ? noteComplement ?? "Bareme reglementaire applique pret par pret a la selection."
      : "Les provisions sont un agregat institution : reserve aux roles DIRECTION, CDG et AUDIT.",
    erreurApi: null,
    selection: { nb_prets: d.nb_prets_selectionnes, noteComplement },
  };
}
