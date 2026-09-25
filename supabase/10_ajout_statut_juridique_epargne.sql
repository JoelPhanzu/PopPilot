-- ============================================================
-- PopPilot — AJOUT : statut juridique du titulaire dans l'inventaire épargne
-- ============================================================
-- ⚠️ STRICTEMENT ADDITIF : IF NOT EXISTS, aucune donnée existante touchée.
--    À exécuter APRÈS 09. Rejouable sans risque.
--    Codes du CBS : 1 = personne physique, 2 = personne morale, 4 = groupe solidaire.
--    Les inventaires importés avant cette colonne n'ont pas de statut : réimporter le mois.
-- ============================================================
ALTER TABLE fait_epargne ADD COLUMN IF NOT EXISTS statut_juridique VARCHAR;
CREATE INDEX IF NOT EXISTS ix_epargne_statut ON fait_epargne(date_arrete, statut_juridique);
