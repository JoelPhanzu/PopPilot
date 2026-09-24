-- ============================================================
-- PopPilot — AJOUT de tables : Eljo Smart + Archives modifiables
-- ============================================================
-- ⚠️ STRICTEMENT ADDITIF : IF NOT EXISTS partout, aucune donnée existante touchée.
--    À exécuter APRÈS 06. Rejouable sans risque.
-- ============================================================

-- ===== ELJO SMART (messagerie) =====
-- Historique des conversations : chaque question + la réponse donnée (traçabilité).
CREATE TABLE IF NOT EXISTS eljo_conversation (
    id            SERIAL PRIMARY KEY,
    auth_uid      UUID,                    -- qui a posé la question
    login         VARCHAR,
    role          VARCHAR,
    agence        VARCHAR,                 -- périmètre au moment de la question
    question      TEXT NOT NULL,
    intention     VARCHAR,                 -- indicateur détecté
    reponse       TEXT,
    valeur        DOUBLE PRECISION,        -- valeur exacte renvoyée (si numérique)
    horodatage    TIMESTAMP DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_eljo_uid ON eljo_conversation(auth_uid);
CREATE INDEX IF NOT EXISTS ix_eljo_date ON eljo_conversation(horodatage);

-- ===== ARCHIVES & HISTORIQUES =====
-- Bibliothèque de rapports (fichiers importés, consultables, REMPLAÇABLES).
CREATE TABLE IF NOT EXISTS archive_rapport (
    id             SERIAL PRIMARY KEY,
    titre          VARCHAR NOT NULL,
    type_rapport   VARCHAR,               -- FINA / AML / portée / indicateurs / autre
    periode        VARCHAR,               -- ex. "2025", "juillet 2026"
    fichier_url    VARCHAR,               -- emplacement (Supabase Storage)
    format         VARCHAR,               -- xlsx / pdf / csv
    version        INTEGER DEFAULT 1,     -- incrémenté à chaque remplacement
    depose_par     VARCHAR,
    date_depot     TIMESTAMP DEFAULT now(),
    remplace_id    INTEGER                -- id de la version précédente (historique)
);
CREATE INDEX IF NOT EXISTS ix_archive_type ON archive_rapport(type_rapport);
CREATE INDEX IF NOT EXISTS ix_archive_periode ON archive_rapport(periode);

-- Séries temporelles d'indicateurs (pour les courbes d'évolution).
-- Alimentée par : (1) import des historiques passés, (2) calculs mensuels de PopPilot.
CREATE TABLE IF NOT EXISTS serie_indicateur (
    id            SERIAL PRIMARY KEY,
    indicateur    VARCHAR NOT NULL,        -- ex. "encours_credit", "par30", "nb_epargnants"
    date_arrete   DATE NOT NULL,
    agence        VARCHAR,                 -- NULL = consolidé
    valeur        DOUBLE PRECISION,
    unite         VARCHAR,                 -- USD / CDF / % / nombre
    source        VARCHAR                  -- "import_historique" / "calcul_poppilot"
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_serie
    ON serie_indicateur(indicateur, date_arrete, COALESCE(agence,''));
CREATE INDEX IF NOT EXISTS ix_serie_ind ON serie_indicateur(indicateur);

-- Archives modifiables EN LIGNE (données éditables cellule par cellule).
-- Pour les fichiers qu'on veut éditer directement (ajout de lignes/colonnes/valeurs).
CREATE TABLE IF NOT EXISTS archive_donnees (
    id            SERIAL PRIMARY KEY,
    archive_id    INTEGER REFERENCES archive_rapport(id),
    ligne         INTEGER NOT NULL,
    colonne       VARCHAR NOT NULL,
    valeur        TEXT,
    modifie_par   VARCHAR,
    modifie_le    TIMESTAMP DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_archdata ON archive_donnees(archive_id);

-- ===== RLS sur les nouvelles tables =====
DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY['eljo_conversation','archive_rapport','serie_indicateur','archive_donnees']
  LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY;', t);
    EXECUTE format('DROP POLICY IF EXISTS %I_select ON %I;', t, t);
    EXECUTE format($f$CREATE POLICY %I_select ON %I FOR SELECT USING (pp_role() IS NOT NULL);$f$, t, t);
    EXECUTE format('DROP POLICY IF EXISTS %I_write ON %I;', t, t);
    EXECUTE format($f$CREATE POLICY %I_write ON %I FOR ALL
      USING (pp_role() IN ('DIRECTION','CDG')) WITH CHECK (pp_role() IN ('DIRECTION','CDG'));$f$, t, t);
  END LOOP;
END $$;

-- Eljo : chaque utilisateur voit SES propres conversations (sauf DIRECTION/CDG)
DROP POLICY IF EXISTS eljo_conversation_select ON eljo_conversation;
CREATE POLICY eljo_conversation_select ON eljo_conversation FOR SELECT USING (
  auth_uid = auth.uid() OR pp_role() IN ('DIRECTION','CDG')
);

-- ✅ Additif, rejouable, aucune donnée existante affectée.
