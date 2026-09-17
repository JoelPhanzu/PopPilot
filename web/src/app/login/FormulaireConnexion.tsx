"use client";

/**
 * PopPilot — formulaire de connexion (Supabase Auth).
 *
 * `signInWithPassword` depose la session dans des cookies lisibles par le
 * serveur (@supabase/ssr). D'ou le `router.refresh()` apres succes : il force
 * le rendu serveur a relire ces cookies, donc a resoudre le role AVANT
 * d'afficher la moindre donnee.
 */
import { useMemo, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { clientNavigateur } from "@/lib/supabase/client";

/** Traduit les messages Supabase, qui arrivent en anglais. */
function messageLisible(brut: string): string {
  const m = brut.toLowerCase();
  if (m.includes("invalid login credentials")) {
    return "Identifiants incorrects. Verifiez l'adresse e-mail et le mot de passe.";
  }
  if (m.includes("email not confirmed")) {
    return "Adresse e-mail non confirmee. Ouvrez le lien recu par courriel.";
  }
  if (m.includes("failed to fetch") || m.includes("networkerror")) {
    return "Supabase injoignable. Verifiez NEXT_PUBLIC_SUPABASE_URL et votre connexion.";
  }
  return brut;
}

export function FormulaireConnexion({ suite }: { suite: string }) {
  const router = useRouter();
  const supabase = useMemo(() => clientNavigateur(), []);
  const [courriel, setCourriel] = useState("");
  const [motDePasse, setMotDePasse] = useState("");
  const [erreur, setErreur] = useState<string | null>(null);
  const [enCours, setEnCours] = useState(false);

  async function soumettre(evenement: FormEvent<HTMLFormElement>) {
    evenement.preventDefault();
    if (supabase === null) return;

    setErreur(null);
    setEnCours(true);
    const { error } = await supabase.auth.signInWithPassword({
      email: courriel.trim(),
      password: motDePasse,
    });

    if (error) {
      setErreur(messageLisible(error.message));
      setEnCours(false);
      return;
    }

    router.replace(suite);
    router.refresh();
  }

  const champ =
    "w-full rounded-lg border border-pop-bord bg-white px-3.5 py-2.5 text-[15px] text-pop-encre " +
    "outline-none transition focus:border-pop-cyan focus:ring-2 focus:ring-pop-cyan/30 " +
    "disabled:bg-pop-fond disabled:text-pop-gris";

  return (
    <form onSubmit={soumettre} className="space-y-4" noValidate>
      <div className="space-y-1.5">
        <label htmlFor="courriel" className="block text-sm font-medium text-pop-gris">
          Adresse e-mail
        </label>
        <input
          id="courriel"
          name="email"
          type="email"
          autoComplete="username"
          required
          disabled={supabase === null || enCours}
          value={courriel}
          onChange={(e) => setCourriel(e.target.value)}
          placeholder="prenom.nom@micropop.cd"
          className={champ}
        />
      </div>

      <div className="space-y-1.5">
        <label htmlFor="motdepasse" className="block text-sm font-medium text-pop-gris">
          Mot de passe
        </label>
        <input
          id="motdepasse"
          name="password"
          type="password"
          autoComplete="current-password"
          required
          disabled={supabase === null || enCours}
          value={motDePasse}
          onChange={(e) => setMotDePasse(e.target.value)}
          placeholder="••••••••"
          className={champ}
        />
      </div>

      {erreur !== null && (
        <p
          role="alert"
          className="rounded-lg border border-pop-danger/25 bg-pop-danger/5 px-3.5 py-2.5 text-sm text-pop-danger"
        >
          {erreur}
        </p>
      )}

      <button
        type="submit"
        disabled={supabase === null || enCours}
        className="w-full rounded-lg bg-pop-bleu px-4 py-2.5 text-[15px] font-semibold text-white transition
                   hover:bg-pop-bleu-2 focus-visible:outline-2 focus-visible:outline-offset-2
                   focus-visible:outline-pop-cyan disabled:cursor-not-allowed disabled:opacity-55"
      >
        {enCours ? "Connexion en cours…" : "Se connecter"}
      </button>
    </form>
  );
}
