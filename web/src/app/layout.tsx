/**
 * PopPilot — mise en page racine.
 *
 * Le theme est fige en clair : un tableau de bord comptable doit avoir le meme
 * rendu sur tous les postes (et a l'impression). Les couleurs de la charte sont
 * declarees dans globals.css.
 *
 * Typographie : pile systeme, declaree dans globals.css. On evite
 * `next/font/google`, qui telecharge la fonte a la compilation et fait donc
 * echouer `build`/`dev` sur un poste ou un serveur sans acces a
 * fonts.gstatic.com — inacceptable pour un outil interne.
 */
import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "PopPilot", template: "%s" },
  description:
    "PopPilot — plateforme de pilotage MICROPOP : credit, epargne, comptabilite, rapports reglementaires.",
  applicationName: "PopPilot",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="fr" className="h-full antialiased">
      <body className="min-h-full font-sans">{children}</body>
    </html>
  );
}
