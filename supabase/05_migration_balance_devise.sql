-- ============================================================
-- PopPilot — MIGRATION : la devise entre dans la clé de fait_balance
-- À exécuter UNE FOIS sur une base déjà créée avec 01_schema.sql.
-- (Une base créée après cette correction a déjà la bonne contrainte.)
-- ============================================================
--
-- POURQUOI : un arrêté porte DEUX balances — la balance USD (bilan, indicateurs,
-- budget) et la balance CDF (FINA, §32-37). Avec l'ancienne contrainte
-- UNIQUE (date_arrete, numero_compte), importer l'une supprimait l'autre, et le
-- bilan « USD » sortait alors des montants CDF (facteur ~2268) SANS erreur visible.
--
-- Contrôle AVANT migration — les lignes sans devise (anciennes) sont des USD :
--   SELECT devise, count(*) FROM fait_balance GROUP BY devise;

BEGIN;

-- 1) Normaliser les lignes anciennes : pas de devise = USD (seule balance d'alors).
UPDATE fait_balance SET devise = 'USD' WHERE devise IS NULL OR devise = '';

-- 2) Remplacer la contrainte d'unicité.
ALTER TABLE fait_balance DROP CONSTRAINT IF EXISTS uq_balance_arrete_compte;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint
                 WHERE conname = 'uq_balance_arrete_compte_devise') THEN
    ALTER TABLE fait_balance
      ADD CONSTRAINT uq_balance_arrete_compte_devise
      UNIQUE (date_arrete, numero_compte, devise);
  END IF;
END $$;

COMMIT;

-- Contrôle APRÈS migration : les deux balances de juillet doivent pouvoir coexister.
--   SELECT date_arrete, devise, count(*), round(sum(solde_net)::numeric, 2)
--   FROM fait_balance GROUP BY date_arrete, devise ORDER BY date_arrete, devise;
