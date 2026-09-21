import type { NextConfig } from "next";

/**
 * TROIS plafonds distincts gouvernent un import, et il faut les tenir ENSEMBLE.
 * Un seul laisse a 10 Mo et l'inventaire epargne (19 Mo) echoue — c'est le
 * defaut qui a produit « Unexpected end of form » : le corps etait coupe a
 * 10 Mo par le proxy, et le parseur multipart de Next (busboy) voyait un
 * formulaire qui s'arretait avant sa frontiere de fin. Le message ne parle ni
 * de taille ni de proxy, d'ou la fausse piste.
 *
 *   1. `proxyClientMaxBodySize` — proxy Next (ex-middleware). DEFAUT : 10 Mo.
 *      C'est le plus bas des trois, et il s'applique a TOUTE requete qui
 *      traverse src/proxy.ts, donc a tous les imports.
 *   2. `serverActions.bodySizeLimit` — action serveur. DEFAUT : 1 Mo.
 *   3. `POPPILOT_IMPORT_MAX_MO` — plafond de l'API (200 Mo par defaut).
 *
 * Les deux premiers sont regles ici, legerement AU-DESSUS du troisieme : c'est
 * l'API qui doit refuser un fichier trop gros, avec un message qui le dit
 * (413 « Relever POPPILOT_IMPORT_MAX_MO »), et non Next avec une erreur de
 * parseur. La marge couvre l'enveloppe multipart (frontieres, en-tetes de
 * parties, metadonnees de champs).
 */
const PLAFOND_IMPORT = "220mb";

const nextConfig: NextConfig = {
  experimental: {
    serverActions: { bodySizeLimit: PLAFOND_IMPORT },
    proxyClientMaxBodySize: PLAFOND_IMPORT,
  },
};

export default nextConfig;
