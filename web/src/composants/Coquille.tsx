/**
 * PopPilot — coquille de l'application : barre laterale bleue, entete, contenu.
 *
 * La barre laterale porte l'identite (bleu principal #0B3D5C sur toute la
 * hauteur) ; le contenu vit sur le fond clair #F4F7FA. Le cyan ne sert qu'a
 * marquer la page courante et les liens.
 *
 * Les domaines pas encore construits sont affiches DESACTIVES plutot que
 * masques : l'utilisateur voit ou va la plateforme, sans croire qu'une page
 * existe deja.
 */
import Link from "next/link";
import type { ReactNode } from "react";
import { Logo, Signature } from "@/composants/Logo";
import { BoutonDeconnexion } from "@/composants/BoutonDeconnexion";
import { LIBELLES_ROLE, aAccesTotal, peutEcrire, porteeAffichee, type Profil } from "@/lib/roles";

/**
 * `ecriture` : entree reservee aux roles qui peuvent alimenter le socle.
 * `total` : entree reservee aux roles a acces total (donnees institutionnelles).
 */
type Entree = { href: string; libelle: string; pret: boolean; ecriture?: boolean; total?: boolean };

const NAVIGATION: Entree[] = [
  { href: "/credit", libelle: "Credit", pret: true },
  { href: "/productivite", libelle: "Productivite", pret: true },
  { href: "/comptabilite", libelle: "Comptabilite & indicateurs", pret: true },
  { href: "/compte-resultat", libelle: "Compte d'exploitation agences", pret: true },
  { href: "/epargne", libelle: "Epargne", pret: true },
  { href: "/budget", libelle: "Budget", pret: true },
  { href: "/rapports", libelle: "Rapports reglementaires", pret: true },
  { href: "/eljo", libelle: "Eljo Smart", pret: true },
  // Primes : nominatives et institutionnelles — DIRECTION, CDG, AUDIT seulement.
  { href: "/primes", libelle: "Primes", pret: true, total: true },
  { href: "/archives", libelle: "Archives", pret: true, total: true },
  // L'import est le point d'entree de la plateforme, mais c'est une ECRITURE :
  // il n'apparait que pour DIRECTION / CDG. Un lien propose puis refuse par
  // l'API donnerait l'impression d'une panne plutot que d'une regle.
  { href: "/import", libelle: "Import CBS", pret: true, ecriture: true },
  { href: "/sage", libelle: "Traitement SAGE", pret: true, ecriture: true },
  // La configuration engage tous les calculs : meme regle que l'import, elle
  // n'apparait que pour les roles qui alimentent le socle.
  { href: "/configuration", libelle: "Configuration", pret: true, ecriture: true },
];

export function Coquille({
  profil,
  actif,
  children,
}: {
  profil: Profil;
  actif: string;
  children: ReactNode;
}) {
  return (
    <div className="flex min-h-dvh flex-col lg:flex-row">
      <aside className="flex shrink-0 flex-col bg-pop-bleu lg:min-h-dvh lg:w-64">
        <div className="flex items-center gap-3 px-5 py-5">
          <Logo taille={40} />
          <div className="min-w-0">
            <p className="text-base font-semibold leading-tight text-white">PopPilot</p>
            <p className="truncate text-[11px] text-white/60">Pilotage MICROPOP</p>
          </div>
        </div>

        <nav className="px-3 pb-4 lg:flex-1" aria-label="Domaines">
          <ul className="space-y-1">
            {NAVIGATION.filter(
              (e) => (!e.ecriture || peutEcrire(profil)) && (!e.total || aAccesTotal(profil)),
            ).map((entree) => {
              const courant = entree.href === actif;
              if (!entree.pret) {
                return (
                  <li key={entree.href}>
                    <span
                      className="flex cursor-not-allowed items-center justify-between rounded-lg px-3 py-2 text-sm text-white/35"
                      title="Domaine a venir"
                    >
                      {entree.libelle}
                      <span className="text-[10px] uppercase tracking-wide">a venir</span>
                    </span>
                  </li>
                );
              }
              return (
                <li key={entree.href}>
                  <Link
                    href={entree.href}
                    aria-current={courant ? "page" : undefined}
                    className={
                      courant
                        ? "flex items-center gap-2 rounded-lg bg-white/10 px-3 py-2 text-sm font-medium text-white " +
                          "shadow-[inset_3px_0_0_0_var(--color-pop-cyan)]"
                        : "flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-white/75 transition hover:bg-white/5 hover:text-white"
                    }
                  >
                    {entree.libelle}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>

        <div className="hidden border-t border-white/10 px-5 py-4 lg:block">
          <Signature className="text-xs text-pop-cyan" />
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex flex-wrap items-center justify-between gap-3 bg-pop-bleu-2 px-5 py-3 lg:px-8">
          <div className="min-w-0">
            <p className="text-sm font-medium text-white">
              {profil.login}
              <span className="ml-2 rounded-full bg-white/15 px-2 py-0.5 text-[11px] font-normal text-white/85">
                {LIBELLES_ROLE[profil.role]}
              </span>
              {profil.demo && (
                <span className="ml-2 rounded-full bg-pop-cyan/20 px-2 py-0.5 text-[11px] font-normal text-white">
                  demonstration
                </span>
              )}
            </p>
            <p className="truncate text-[11px] text-white/70">
              Perimetre&nbsp;: {porteeAffichee(profil)}
            </p>
          </div>
          <BoutonDeconnexion demo={profil.demo} />
        </header>

        <main className="flex-1 px-5 py-6 lg:px-8 lg:py-8">{children}</main>
      </div>
    </div>
  );
}
