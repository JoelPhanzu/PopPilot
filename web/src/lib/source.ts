/**
 * PopPilot — provenance des chiffres affiches.
 *
 * Type commun a tous les domaines (credit, comptabilite, epargne…) : il vit
 * ici et non dans l'un d'eux, parce qu'il n'appartient a aucun. Le bandeau qui
 * l'affiche (BandeauSource) est lui aussi partage.
 *
 * Regle de la maison : un chiffre issu du mode demonstration ne doit jamais
 * pouvoir passer pour un chiffre du socle. D'ou ce marqueur, transporte
 * jusqu'a l'ecran plutot que devine a l'arrivee.
 */
export type SourceDonnees = "api" | "demonstration";
