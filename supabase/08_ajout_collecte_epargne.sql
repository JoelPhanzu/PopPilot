-- ============================================================
-- PopPilot — AJOUT : collecte d'épargne mensuelle (prime des superviseurs épargne)
-- ============================================================
-- ⚠️ STRICTEMENT ADDITIF : IF NOT EXISTS partout, aucune donnée existante touchée.
--    À exécuter APRÈS 07. Rejouable sans risque.
-- ============================================================

-- Fichier mensuel Agence | Cible | Réalisation, rangé à son MOIS (date_arrete = dernier jour).
CREATE TABLE IF NOT EXISTS fait_collecte_epargne (
    id            SERIAL PRIMARY KEY,
    date_arrete   DATE NOT NULL,
    agence        VARCHAR NOT NULL,
    cible         DOUBLE PRECISION,
    realisation   DOUBLE PRECISION,
    fichier       VARCHAR,
    importe_par   VARCHAR,
    horodatage    TIMESTAMP DEFAULT now(),
    CONSTRAINT uq_collecte_epargne UNIQUE (date_arrete, agence)
);
CREATE INDEX IF NOT EXISTS ix_collecte_epargne_date ON fait_collecte_epargne(date_arrete);

-- RLS : lecture réservée à DIRECTION, CDG et AUDIT (primes nominatives) ; écriture par l'API seule (rôle postgres).
ALTER TABLE fait_collecte_epargne ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS fait_collecte_epargne_select ON fait_collecte_epargne;
CREATE POLICY fait_collecte_epargne_select ON fait_collecte_epargne
    FOR SELECT USING (pp_role() IN ('DIRECTION', 'CDG', 'AUDIT'));
