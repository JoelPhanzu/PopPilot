-- ============================================================
-- PopPilot — Authentification liée à Supabase + Row Level Security
-- À exécuter APRÈS 01_schema.sql, dans l'éditeur SQL de Supabase.
-- ============================================================

-- 1) Lier la table utilisateur aux comptes Supabase (auth.users)
ALTER TABLE utilisateur ADD COLUMN IF NOT EXISTS auth_uid uuid REFERENCES auth.users(id);
CREATE INDEX IF NOT EXISTS ix_utilisateur_auth_uid ON utilisateur(auth_uid);

-- 2) Fonctions d'aide : rôle et agence de l'utilisateur connecté
--    (SECURITY DEFINER pour lire la table utilisateur sans être bloqué par RLS)
CREATE OR REPLACE FUNCTION pp_role() RETURNS text
LANGUAGE sql STABLE SECURITY DEFINER AS $$
  SELECT role FROM utilisateur WHERE auth_uid = auth.uid() AND actif = true LIMIT 1;
$$;

CREATE OR REPLACE FUNCTION pp_agence() RETURNS text
LANGUAGE sql STABLE SECURITY DEFINER AS $$
  SELECT agence FROM utilisateur WHERE auth_uid = auth.uid() AND actif = true LIMIT 1;
$$;

-- pp_acces_total : vrai pour DIRECTION, CDG, AUDIT (voient toutes les agences)
CREATE OR REPLACE FUNCTION pp_acces_total() RETURNS boolean
LANGUAGE sql STABLE AS $$
  SELECT pp_role() IN ('DIRECTION','CDG','AUDIT');
$$;

-- 3) RLS sur les tables cloisonnées par agence
--    Règle : accès total (DIRECTION/CDG/AUDIT) OU (rôle AGENCE ET ligne de son agence).
DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY[
    'fait_credit','fait_epargne','fait_budget','fait_prime',
    'fait_remboursement_attendu','param_objectif','provision_manuelle','dim_employe'
  ]
  LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY;', t);
    EXECUTE format('DROP POLICY IF EXISTS %I_select ON %I;', t, t);
    EXECUTE format($f$
      CREATE POLICY %I_select ON %I FOR SELECT USING (
        pp_acces_total()
        OR (pp_role() = 'AGENCE' AND agence = pp_agence())
      );
    $f$, t, t);
    -- écriture réservée à DIRECTION/CDG (import, calculs)
    EXECUTE format('DROP POLICY IF EXISTS %I_write ON %I;', t, t);
    EXECUTE format($f$
      CREATE POLICY %I_write ON %I FOR ALL USING (
        pp_role() IN ('DIRECTION','CDG')
      ) WITH CHECK (
        pp_role() IN ('DIRECTION','CDG')
      );
    $f$, t, t);
  END LOOP;
END $$;

-- 4) RLS sur les tables SANS agence (balance, GL, transactions, dimensions, paramètres)
--    Lecture : tout utilisateur authentifié actif. Écriture : DIRECTION/CDG.
DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY[
    'fait_balance','fait_grand_livre','fait_remboursement_realise','fait_transaction_caisse',
    'dim_agence','dim_client','dim_plan_comptable','dim_produit_credit','dim_produit_epargne',
    'import_log','mapping_budget','param_bareme_prime','param_bareme_provision',
    'param_calendrier_ouvre','param_mapping_compte','param_mapping_fina','param_mapping_libelle',
    'param_norme_bcc','param_reintegration','param_taux_change','param_taux_ibp'
  ]
  LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY;', t);
    EXECUTE format('DROP POLICY IF EXISTS %I_select ON %I;', t, t);
    EXECUTE format($f$
      CREATE POLICY %I_select ON %I FOR SELECT USING (pp_role() IS NOT NULL);
    $f$, t, t);
    EXECUTE format('DROP POLICY IF EXISTS %I_write ON %I;', t, t);
    EXECUTE format($f$
      CREATE POLICY %I_write ON %I FOR ALL USING (pp_role() IN ('DIRECTION','CDG'))
      WITH CHECK (pp_role() IN ('DIRECTION','CDG'));
    $f$, t, t);
  END LOOP;
END $$;

-- 5) RLS sur la table utilisateur elle-même
ALTER TABLE utilisateur ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS utilisateur_self ON utilisateur;
CREATE POLICY utilisateur_self ON utilisateur FOR SELECT USING (
  auth_uid = auth.uid() OR pp_role() IN ('DIRECTION','CDG')
);
DROP POLICY IF EXISTS utilisateur_admin ON utilisateur;
CREATE POLICY utilisateur_admin ON utilisateur FOR ALL USING (pp_role() = 'DIRECTION')
  WITH CHECK (pp_role() = 'DIRECTION');
