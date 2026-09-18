import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  experimental: {
    /**
     * Les extractions du CBS passent par une action serveur (/import) : le
     * fichier traverse donc le serveur Next avant d'atteindre l'API. La limite
     * par defaut des actions serveur est de 1 Mo — un inventaire epargne
     * (~170 000 comptes) serait refuse AVANT meme d'arriver au moteur, avec un
     * message qui ne parle ni d'import ni de taille.
     *
     * A garder coherent avec POPPILOT_IMPORT_MAX_MO cote API (200 Mo par
     * defaut) : la marge couvre l'enveloppe multipart.
     */
    serverActions: { bodySizeLimit: "220mb" },
  },
};

export default nextConfig;
