-- ============================================================
-- PopPilot — Authentification liée à Supabase + Row Level Security
-- À exécuter APRÈS 01_schema.sql, dans l'éditeur SQL de Supabase.
-- ============================================================

-- 1) Lier la table utilisateur aux comptes Supabase (auth.users)
ALTER TABLE utilisateur ADD COLUMN IF NOT EXISTS auth_uid uuid REFERENCES auth.users(id);
CREATE INDEX IF NOT EXISTS ix_utilisateur_auth_uid ON utilisateur(auth_uid);
-- UNIQUE : deux lignes portant le même auth_uid rendraient pp_role() non
-- déterministe (SELECT ... LIMIT 1 sans ORDER BY ci-dessous) : le rôle retenu
-- serait tiré au hasard, y compris un DIRECTION face à un AGENCE.
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'utilisateur_auth_uid_key') THEN
    ALTER TABLE utilisateur ADD CONSTRAINT utilisateur_auth_uid_key UNIQUE (auth_uid);
  END IF;
END $$;

-- 2) Fonctions d'aide : rôle et agence de l'utilisateur connecté
--    (SECURITY DEFINER pour lire la table utilisateur sans être bloqué par RLS)
--    SET search_path : une fonction SECURITY DEFINER s'exécute avec les droits de son
--    propriétaire ; sans search_path figé, elle résout « utilisateur » dans le schéma
--    que l'appelant a mis en tête de SON search_path. On l'épingle donc sur public.
CREATE OR REPLACE FUNCTION pp_role() RETURNS text
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
  SELECT role FROM utilisateur WHERE auth_uid = auth.uid() AND actif = true LIMIT 1;
$$;

CREATE OR REPLACE FUNCTION pp_agence() RETURNS text
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
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

-- 4) RLS sur les tables SANS colonne agence — DEUX NIVEAUX, pas un seul.
--
--    Ces tables ne portent pas d'agence : impossible de les cloisonner ligne à ligne.
--    Les ouvrir à « tout utilisateur authentifié » revenait donc à donner à un chef
--    d'agence la comptabilité de toute l'institution (fait_balance, fait_grand_livre),
--    les opérations de caisse nominatives (fait_transaction_caisse.nom_client) et le
--    référentiel client complet (dim_client) — y compris les clients des autres agences.
--    L'API, elle, réserve déjà ces agrégats aux rôles à accès total (exiger_role) :
--    le RLS était le maillon le plus large. On aligne les deux.
--
-- 4a) Données comptables et nominatives : réservées aux rôles à accès total.
DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY[
    'fait_balance','fait_grand_livre','fait_remboursement_realise','fait_transaction_caisse',
    'dim_client','import_log'
  ]
  LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY;', t);
    EXECUTE format('DROP POLICY IF EXISTS %I_select ON %I;', t, t);
    EXECUTE format($f$
      CREATE POLICY %I_select ON %I FOR SELECT USING (pp_acces_total());
    $f$, t, t);
    EXECUTE format('DROP POLICY IF EXISTS %I_write ON %I;', t, t);
    EXECUTE format($f$
      CREATE POLICY %I_write ON %I FOR ALL USING (pp_role() IN ('DIRECTION','CDG'))
      WITH CHECK (pp_role() IN ('DIRECTION','CDG'));
    $f$, t, t);
  END LOOP;
END $$;

-- 4b) Référentiels et paramètres (barèmes, taux, mappings, calendrier, produits) :
--     lecture par tout utilisateur actif — ils ne contiennent aucune donnée client et
--     servent à interpréter ses propres chiffres. Écriture : DIRECTION/CDG.
DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY[
    'dim_agence','dim_plan_comptable','dim_produit_credit','dim_produit_epargne',
    'mapping_budget','param_bareme_prime','param_bareme_provision',
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
