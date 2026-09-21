/**
 * PopPilot — RAPPORTS REGLEMENTAIRES (BCC).
 *
 * Trois declarations, produites par les moteurs valides : FINA (gabarit MFII),
 * AML / LBC-FT, et le systeme de paiement. Le formulaire de chacune est
 * construit a partir du catalogue de l'API — fichiers attendus, extensions,
 * champs et aides viennent du cote qui sait de quoi les moteurs ont besoin.
 *
 * ACCES : rôles a acces total, AUDIT compris. Generer LIT le socle et les
 * fichiers fournis ; rien n'est ecrit. Recalculer une declaration pour la
 * verifier est le travail d'un controleur, et cela ne modifie rien — c'est la
 * difference avec l'import et la configuration, qui restent fermes a l'AUDIT.
 *
 * CE QUE L'ECRAN DOIT DIRE, et qu'il dit : lequel de ces documents est la
 * declaration officielle, et lequel n'est qu'un classeur de resultats. Le
 * systeme de paiement est dans le second cas — le depot ne contient pas de
 * remplisseur pour son gabarit — et quelqu'un qui telecharge un fichier bien
 * nomme pourrait sinon le transmettre en croyant tenir la declaration.
 */
import type { Metadata } from "next";
import { redirect } from "next/navigation";
import Link from "next/link";
import { Coquille } from "@/composants/Coquille";
import { FournisseurSession } from "@/composants/ContexteSession";
import { FormulaireRapport } from "@/composants/FormulaireRapport";
import { sessionCourante } from "@/lib/session";
import { appelerApi } from "@/lib/api";
import { aAccesTotal } from "@/lib/roles";
import type { CatalogueRapports } from "@/lib/rapports";

export const metadata: Metadata = {
  title: "Rapports reglementaires — PopPilot",
  description: "FINA, AML / LBC-FT et systeme de paiement, produits depuis le socle.",
};

export const dynamic = "force-dynamic";

export default async function PageRapports() {
  const { profil, jeton, avertissement } = await sessionCourante();

  if (profil === null) {
    if (avertissement) {
      return (
        <main className="flex min-h-dvh items-center justify-center bg-pop-bleu px-4">
          <div className="max-w-md rounded-2xl bg-white p-7 shadow-2xl">
            <h1 className="text-lg font-semibold text-pop-encre">Acces impossible</h1>
            <p className="mt-2 text-sm leading-relaxed text-pop-gris">{avertissement}</p>
            <a href="/login" className="lien-pop mt-4 inline-block text-sm font-medium">
              Retour a la connexion
            </a>
          </div>
        </main>
      );
    }
    redirect("/login?suite=/rapports");
  }

  if (!aAccesTotal(profil)) {
    return (
      <FournisseurSession profil={profil}>
        <Coquille profil={profil} actif="/rapports">
          <div className="max-w-2xl space-y-4">
            <h1 className="text-2xl font-semibold tracking-tight text-pop-encre">
              Rapports reglementaires
            </h1>
            <div className="rounded-xl border border-pop-bord bg-pop-carte px-5 py-4 shadow-sm">
              <p className="text-[13px] font-semibold text-pop-encre">
                Domaine reserve aux roles d&apos;institution
              </p>
              <p className="mt-1.5 text-[13px] leading-relaxed text-pop-gris">
                Les declarations a la BCC portent sur l&apos;institution entiere : elles ne
                se decoupent pas par agence, et sont reservees aux roles DIRECTION, CDG
                et AUDIT.
              </p>
              <Link href="/credit" className="lien-pop mt-3 inline-block text-[13px] font-medium">
                Aller au tableau de bord credit
              </Link>
            </div>
          </div>
        </Coquille>
      </FournisseurSession>
    );
  }

  const catalogue = await appelerApi<CatalogueRapports>("/rapports", jeton);

  return (
    <FournisseurSession profil={profil}>
      <Coquille profil={profil} actif="/rapports">
        <div className="space-y-6">
          <header>
            <h1 className="text-2xl font-semibold tracking-tight text-pop-encre">
              Rapports reglementaires
            </h1>
            <p className="mt-1 max-w-3xl text-sm leading-relaxed text-pop-gris">
              Les documents sont produits par les moteurs valides, a partir du socle et
              des fichiers fournis. Rien n&apos;est ecrit dans la base&nbsp;: une
              generation lit, elle n&apos;alimente pas.
            </p>
          </header>

          {/* Le taux n'est jamais fige : sans lui, la generation echoue, et il faut
              savoir ou le saisir. Le dire ICI evite un aller-retour. */}
          <div className="rounded-xl border border-pop-bord bg-pop-carte px-5 py-4 shadow-sm">
            <p className="text-[13px] font-semibold text-pop-encre">
              Avant de generer, deux prealables
            </p>
            <ul className="mt-1.5 space-y-1 text-[13px] leading-relaxed text-pop-gris">
              <li>
                <strong>Le taux USD→CDF de la periode doit etre saisi.</strong> FINA et
                AML se declarent en CDF. La plateforme refuse de figer un taux — un taux
                fige produirait un rapport faux d&apos;un facteur ~2268 sans lever la
                moindre alerte, et ce rapport partirait a la banque centrale.{" "}
                <Link href="/configuration" className="lien-pop font-medium">
                  Saisir le taux
                </Link>
              </li>
              <li>
                <strong>Les donnees de la periode doivent etre importees</strong> —
                pour le FINA, la balance <em>CDF</em> de l&apos;arrete, que la balance USD
                ne remplace pas.{" "}
                <Link href="/import" className="lien-pop font-medium">
                  Importer
                </Link>
              </li>
            </ul>
          </div>

          {catalogue.ok ? (
            catalogue.donnees.rapports.map((r) => (
              <FormulaireRapport key={r.cle} rapport={r} />
            ))
          ) : (
            <div className="rounded-xl border border-pop-danger/30 bg-pop-danger/5 px-4 py-3 text-sm text-pop-danger">
              <p className="font-semibold">
                Catalogue des rapports indisponible&nbsp;: aucun formulaire ne peut etre
                construit.
              </p>
              <p className="mt-1 text-[13px] leading-relaxed">{catalogue.erreur}</p>
              <p className="mt-1 text-[13px] leading-relaxed">
                Les champs attendus par chaque rapport viennent de l&apos;API&nbsp;: les
                deviner ici ferait une seconde liste, qui finirait par contredire les
                moteurs.
              </p>
            </div>
          )}
        </div>
      </Coquille>
    </FournisseurSession>
  );
}
