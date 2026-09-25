-- ============================================================
-- PopPilot — AJOUT : nom complet du client dans l'inventaire épargne (Top épargnants)
-- ============================================================
-- ⚠️ STRICTEMENT ADDITIF : IF NOT EXISTS, aucune donnée existante touchée.
--    À exécuter APRÈS 08. Rejouable sans risque.
--    Les inventaires importés AVANT cette colonne n'ont pas de nom : réimporter le
--    mois concerné (page Import, domaine « epargne ») pour le renseigner.
-- ============================================================
ALTER TABLE fait_epargne ADD COLUMN IF NOT EXISTS nom_client VARCHAR;
