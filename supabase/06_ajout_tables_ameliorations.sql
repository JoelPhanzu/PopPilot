-- ============================================================
-- PopPilot — AJOUT de tables pour les améliorations (chantiers 1-7)
-- ============================================================
-- ⚠️ STRICTEMENT ADDITIF : ne recrée AUCUNE table existante, n'efface AUCUNE donnée.
--    Toutes les créations utilisent IF NOT EXISTS.
--    À exécuter dans Supabase APRÈS 01→05, sans risque pour les données en place.
-- ============================================================

-- Chantier 3 : compte de résultat par agence (donnée mensuelle fournie par le CDG)
CREATE TABLE IF NOT EXISTS compte_resultat_agence (
    id            SERIAL PRIMARY KEY,
    date_arrete   DATE NOT NULL,
    poste         VARCHAR NOT NULL,        -- ex. "INTERETS SUR PRETS", "TOTAL PRODUITS"...
    agence        VARCHAR NOT NULL,
    montant       DOUBLE PRECISION,
    devise        VARCHAR DEFAULT 'USD'
);
CREATE INDEX IF NOT EXISTS ix_cra_arrete ON compte_resultat_agence(date_arrete);
CREATE INDEX IF NOT EXISTS ix_cra_agence ON compte_resultat_agence(agence);
CREATE UNIQUE INDEX IF NOT EXISTS uq_cra ON compte_resultat_agence(date_arrete, poste, agence);

-- Chantiers 1,2 : intérêts / remboursements encaissés (source du recouvrement + productivité)
CREATE TABLE IF NOT EXISTS fait_remboursement_encaisse (
    id                    SERIAL PRIMARY KEY,
    date_arrete           DATE NOT NULL,          -- mois de rattachement
    date_remboursement    DATE,
    numero_dossier        VARCHAR NOT NULL,
    numero_client         VARCHAR,
    numero_echeance       VARCHAR,
    capital_rembourse     DOUBLE PRECISION,
    interets_rembourses   DOUBLE PRECISION,
    penalites_rembourses  DOUBLE PRECISION,
    -- hiérarchie résolue à l'import via jointure avec fait_credit (n° dossier) :
    agent_credit          VARCHAR,
    superviseur           VARCHAR,
    agence                VARCHAR
);
CREATE INDEX IF NOT EXISTS ix_remb_arrete ON fait_remboursement_encaisse(date_arrete);
CREATE INDEX IF NOT EXISTS ix_remb_dossier ON fait_remboursement_encaisse(numero_dossier);
CREATE INDEX IF NOT EXISTS ix_remb_agent ON fait_remboursement_encaisse(agent_credit);

-- Chantier 5 : journal des opérations CBS retraité pour SAGE (traçabilité des imports)
CREATE TABLE IF NOT EXISTS journal_sage_traite (
    id             SERIAL PRIMARY KEY,
    date_traitement DATE NOT NULL,
    periode        VARCHAR,
    fichier_source VARCHAR,
    lignes_entree  INTEGER,
    lignes_sortie  INTEGER,
    statut         VARCHAR,                -- OK / ALERTE / ECHEC
    message        VARCHAR
);

-- Chantier 4 : résultat du calcul des primes (historisé par période)
--   (la table fait_prime existe déjà pour le stockage ; on ajoute une table de PARAMÈTRES
--    de campagne de prime si besoin d'historiser les règles appliquées à une période)
CREATE TABLE IF NOT EXISTS campagne_prime (
    id            SERIAL PRIMARY KEY,
    periode       DATE NOT NULL,
    date_calcul   DATE,
    parametres    JSONB,                   -- snapshot du barème appliqué (traçabilité)
    valide_par    VARCHAR
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_campagne_prime ON campagne_prime(periode);

-- ============================================================
-- Activer RLS sur les nouvelles tables (cohérence avec l'existant)
-- ============================================================
DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY[
    'compte_resultat_agence','fait_remboursement_encaisse','journal_sage_traite','campagne_prime'
  ]
  LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY;', t);
    -- lecture : tout utilisateur authentifié (le filtre agence fin se fait dans l'API)
    EXECUTE format('DROP POLICY IF EXISTS %I_select ON %I;', t, t);
    EXECUTE format($f$CREATE POLICY %I_select ON %I FOR SELECT USING (pp_role() IS NOT NULL);$f$, t, t);
    -- écriture : DIRECTION / CDG
    EXECUTE format('DROP POLICY IF EXISTS %I_write ON %I;', t, t);
    EXECUTE format($f$CREATE POLICY %I_write ON %I FOR ALL
      USING (pp_role() IN ('DIRECTION','CDG')) WITH CHECK (pp_role() IN ('DIRECTION','CDG'));$f$, t, t);
  END LOOP;
END $$;

-- ✅ Ce script est rejouable : IF NOT EXISTS partout, aucune donnée existante touchée.
