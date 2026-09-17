/**
 * PopPilot — mise en forme des nombres et des dates (conventions FR / RDC).
 *
 * Un espace insecable etroit separe les milliers : « 10 813 894,00 ». On fige
 * la locale fr-FR pour que le serveur et le navigateur produisent EXACTEMENT
 * la meme chaine — sinon React signale une erreur d'hydratation, et surtout un
 * chiffre comptable ne doit pas changer d'apparence selon le poste.
 */

const MONTANT = new Intl.NumberFormat("fr-FR", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});
const ENTIER = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 0 });
const POURCENT = new Intl.NumberFormat("fr-FR", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

/** Montant a deux decimales : 10 813 894,00 */
export function montant(valeur: number | null | undefined): string {
  if (valeur === null || valeur === undefined || !Number.isFinite(valeur)) return "—";
  return MONTANT.format(valeur);
}

/** Montant + devise : 10 813 894,00 USD */
export function montantDevise(valeur: number | null | undefined, devise = "USD"): string {
  if (valeur === null || valeur === undefined || !Number.isFinite(valeur)) return "—";
  return `${MONTANT.format(valeur)} ${devise}`;
}

/** Forme compacte pour les etiquettes de graphique : 1,19 M / 331,0 k */
export function montantCompact(valeur: number | null | undefined): string {
  if (valeur === null || valeur === undefined || !Number.isFinite(valeur)) return "—";
  const abs = Math.abs(valeur);
  if (abs >= 1_000_000) return `${(valeur / 1_000_000).toFixed(2).replace(".", ",")} M`;
  if (abs >= 1_000) return `${(valeur / 1_000).toFixed(1).replace(".", ",")} k`;
  return MONTANT.format(valeur);
}

export function entier(valeur: number | null | undefined): string {
  if (valeur === null || valeur === undefined || !Number.isFinite(valeur)) return "—";
  return ENTIER.format(valeur);
}

/**
 * Taux en pourcentage. L'API renvoie deja des pourcentages (pct_par30 = 10.99),
 * pas des fractions : on ne multiplie donc PAS par 100.
 */
export function pourcent(valeur: number | null | undefined): string {
  if (valeur === null || valeur === undefined || !Number.isFinite(valeur)) return "—";
  return `${POURCENT.format(valeur)} %`;
}

/** Part d'un total, en pourcentage — protege de la division par zero. */
export function part(numerateur: number, denominateur: number): number | null {
  if (!Number.isFinite(numerateur) || !Number.isFinite(denominateur) || denominateur === 0) {
    return null;
  }
  return (numerateur / denominateur) * 100;
}

/** 2026-05-30 → 30 mai 2026 (sans passer par Date : pas de decalage de fuseau). */
export function dateLongue(iso: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
  if (!m) return iso;
  const mois = ["janvier", "fevrier", "mars", "avril", "mai", "juin",
    "juillet", "aout", "septembre", "octobre", "novembre", "decembre"];
  return `${Number(m[3])} ${mois[Number(m[2]) - 1]} ${m[1]}`;
}

/** Valide une date d'arrete AAAA-MM-JJ (meme controle que `_d()` cote API). */
export function dateArreteValide(iso: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(iso)) return false;
  const d = new Date(`${iso}T00:00:00Z`);
  return !Number.isNaN(d.getTime()) && d.toISOString().slice(0, 10) === iso;
}
