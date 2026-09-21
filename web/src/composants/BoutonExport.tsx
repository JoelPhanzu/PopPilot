/**
 * PopPilot — bouton de telechargement de l'export Excel.
 *
 * Un simple lien, et c'est voulu : le navigateur gere le telechargement, sa
 * progression et son enregistrement. Un bouton JavaScript qui bufferiserait le
 * classeur en memoire avant de le rendre ferait moins bien, et mal sur un
 * export lourd.
 *
 * Le lien porte L'ARRETE AFFICHE : on exporte ce qu'on regarde, jamais un
 * arrete par defaut. C'est ce qui garantit qu'un classeur transmis correspond
 * a l'ecran dont il a ete tire.
 */
import Link from "next/link";

export function BoutonExport({
  domaine,
  arrete,
  libelle = "Exporter en Excel",
  parametres,
}: {
  domaine: "credit" | "comptabilite" | "epargne" | "budget";
  arrete: string;
  libelle?: string;
  /** Parametres propres au domaine (ex. hypothese budgetaire). */
  parametres?: Record<string, string | undefined>;
}) {
  const requete = new URLSearchParams({ arrete });
  for (const [cle, valeur] of Object.entries(parametres ?? {})) {
    if (valeur) requete.set(cle, valeur);
  }

  return (
    <Link
      href={`/api/export/${domaine}?${requete}`}
      // `download` ne suffit pas : c'est l'en-tete Content-Disposition de l'API
      // qui nomme le fichier. L'attribut reste utile pour que le navigateur
      // n'essaie pas d'ouvrir le classeur dans un onglet.
      download
      prefetch={false}
      className="inline-flex items-center gap-2 rounded-lg border border-pop-bord bg-pop-carte px-3.5 py-2
                 text-[13px] font-medium text-pop-bleu-2 shadow-sm transition
                 hover:bg-pop-fond focus-visible:outline-2 focus-visible:outline-offset-2
                 focus-visible:outline-pop-cyan"
    >
      <span aria-hidden className="text-[15px] leading-none">↓</span>
      {libelle}
    </Link>
  );
}
