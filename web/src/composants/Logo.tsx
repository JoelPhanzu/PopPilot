"use client";

/**
 * PopPilot — logo MICROPOP.
 *
 * Le fichier reel est `public/logo_micropop.jpg` (copie depuis assets/). S'il
 * est absent d'un deploiement, on retombe sur un monogramme dessine en CSS :
 * une entete de tableau de bord ne doit jamais afficher une image cassee.
 */
import Image from "next/image";
import { useState } from "react";

export function Logo({
  taille = 44,
  className = "",
}: {
  taille?: number;
  className?: string;
}) {
  const [echec, setEchec] = useState(false);

  if (echec) {
    return (
      <span
        className={`inline-flex items-center justify-center rounded-lg bg-white font-semibold text-pop-bleu ${className}`}
        style={{ width: taille, height: taille, fontSize: taille * 0.38 }}
        aria-hidden
      >
        MP
      </span>
    );
  }

  return (
    <Image
      src="/logo_micropop.jpg"
      alt="MICROPOP"
      width={taille}
      height={taille}
      priority
      onError={() => setEchec(true)}
      className={`rounded-lg bg-white object-contain ${className}`}
      style={{ width: taille, height: taille }}
    />
  );
}

/** Signature de marque — « Je reve, je realise ». */
export function Signature({ className = "" }: { className?: string }) {
  return (
    <p className={`italic tracking-wide ${className}`}>&laquo;&nbsp;Je r&ecirc;ve, je r&eacute;alise&nbsp;&raquo;</p>
  );
}
