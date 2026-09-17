-- SCHEMA SUPABASE (PostgreSQL) — Plateforme MICROPOP
-- Généré depuis le modèle validé. À exécuter dans l'éditeur SQL de Supabase.
-- Les tables de FAITS sont volumineuses (crédit ~8k/mois, épargne ~170k) → index sur date_arrete.

CREATE TABLE dim_agence (
	id SERIAL NOT NULL, 
	code_agence VARCHAR NOT NULL, 
	nom VARCHAR, 
	region VARCHAR, 
	date_ouverture DATE, 
	statut VARCHAR, 
	date_fermeture DATE, 
	motif VARCHAR, 
	PRIMARY KEY (id), 
	UNIQUE (code_agence)
);

CREATE TABLE dim_client (
	id SERIAL NOT NULL, 
	numero_client VARCHAR NOT NULL, 
	nom VARCHAR, 
	sexe VARCHAR, 
	secteur VARCHAR, 
	ville VARCHAR, 
	statut_juridique VARCHAR, 
	PRIMARY KEY (id), 
	UNIQUE (numero_client)
);

CREATE TABLE dim_employe (
	id SERIAL NOT NULL, 
	nom VARCHAR NOT NULL, 
	fonction VARCHAR, 
	agence VARCHAR, 
	date_debut DATE, 
	date_fin DATE, 
	PRIMARY KEY (id)
);

CREATE TABLE dim_plan_comptable (
	id SERIAL NOT NULL, 
	numero VARCHAR NOT NULL, 
	libelle VARCHAR, 
	prefixe VARCHAR, 
	agregat VARCHAR, 
	PRIMARY KEY (id), 
	UNIQUE (numero)
);

CREATE TABLE dim_produit_credit (
	id SERIAL NOT NULL, 
	produit VARCHAR NOT NULL, 
	est_groupe BOOLEAN, 
	secteur VARCHAR, 
	PRIMARY KEY (id), 
	UNIQUE (produit)
);

CREATE TABLE dim_produit_epargne (
	id SERIAL NOT NULL, 
	id_prod VARCHAR NOT NULL, 
	libelle VARCHAR, 
	type_depot VARCHAR, 
	est_groupe BOOLEAN, 
	compte_bcc VARCHAR, 
	PRIMARY KEY (id), 
	UNIQUE (id_prod)
);

CREATE TABLE fait_balance (
	id SERIAL NOT NULL, 
	date_arrete DATE NOT NULL, 
	date_snapshot DATE NOT NULL, 
	numero_compte VARCHAR NOT NULL, 
	libelle VARCHAR, 
	debit_initial FLOAT, 
	credit_initial FLOAT, 
	debit_mvmt FLOAT, 
	credit_mvmt FLOAT, 
	solde_net FLOAT, 
	devise VARCHAR, 
	PRIMARY KEY (id), 
	-- La DEVISE fait partie de la clé : la balance USD (bilan, indicateurs, budget)
	-- et la balance CDF (FINA) du même arrêté coexistent sans jamais s'écraser.
	CONSTRAINT uq_balance_arrete_compte_devise UNIQUE (date_arrete, numero_compte, devise)
);

CREATE TABLE fait_budget (
	id SERIAL NOT NULL, 
	exercice INTEGER NOT NULL, 
	hypothese VARCHAR, 
	agence VARCHAR, 
	ligne_budgetaire VARCHAR, 
	produit VARCHAR, 
	mois INTEGER, 
	montant_budgete FLOAT, 
	type VARCHAR, 
	PRIMARY KEY (id)
);

CREATE TABLE fait_credit (
	id SERIAL NOT NULL, 
	date_arrete DATE NOT NULL, 
	date_snapshot DATE NOT NULL, 
	numero_dossier VARCHAR NOT NULL, 
	numero_client VARCHAR, 
	nom_client VARCHAR, 
	produit_credit VARCHAR, 
	est_groupe BOOLEAN, 
	agence VARCHAR, 
	agent_credit VARCHAR, 
	superviseur VARCHAR, 
	id_groupe VARCHAR, 
	nom_groupe VARCHAR, 
	sexe VARCHAR, 
	montant_debourse FLOAT, 
	date_deboursement DATE, 
	date_fin_echeance DATE, 
	duree FLOAT, 
	taux_interet FLOAT, 
	frequence VARCHAR, 
	encours FLOAT, 
	interets FLOAT, 
	interets_retard FLOAT, 
	penalites FLOAT, 
	jours_de_retard INTEGER, 
	capital_retard FLOAT, 
	impayes FLOAT, 
	garantie FLOAT, 
	tr_1_7 FLOAT, 
	tr_8_30 FLOAT, 
	tr_31_60 FLOAT, 
	tr_61_90 FLOAT, 
	tr_91_180 FLOAT, 
	tr_181_360 FLOAT, 
	tr_361_plus FLOAT, 
	devise VARCHAR, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_credit_arrete_dossier UNIQUE (date_arrete, numero_dossier)
);

CREATE TABLE fait_epargne (
	id SERIAL NOT NULL, 
	date_arrete DATE NOT NULL, 
	date_snapshot DATE NOT NULL, 
	id_compte VARCHAR NOT NULL, 
	num_complet_cpte VARCHAR, 
	id_client VARCHAR, 
	id_prod VARCHAR, 
	libelle_produit VARCHAR, 
	agence VARCHAR, 
	devise VARCHAR, 
	solde_actuel FLOAT, 
	solde_debut FLOAT, 
	solde_fin FLOAT, 
	montant_depot FLOAT, 
	montant_retrait FLOAT, 
	sexe VARCHAR, 
	secteur_activite VARCHAR, 
	ville VARCHAR, 
	date_ouverture DATE, 
	est_groupe BOOLEAN, 
	type_depot VARCHAR, 
	PRIMARY KEY (id)
);

CREATE TABLE fait_grand_livre (
	id SERIAL NOT NULL, 
	date_arrete DATE NOT NULL, 
	date_snapshot DATE NOT NULL, 
	date_ecriture DATE, 
	numero_compte VARCHAR NOT NULL, 
	ligne_budgetaire VARCHAR, 
	mois VARCHAR, 
	libelle VARCHAR, 
	devise VARCHAR, 
	montant FLOAT, 
	PRIMARY KEY (id)
);

CREATE TABLE fait_prime (
	id SERIAL NOT NULL, 
	periode DATE NOT NULL, 
	employe VARCHAR NOT NULL, 
	fonction VARCHAR, 
	agence VARCHAR, 
	base_volume FLOAT, 
	base_nombre FLOAT, 
	base_couverture FLOAT, 
	par_agent FLOAT, 
	correcteur_par FLOAT, 
	prime_calculee FLOAT, 
	PRIMARY KEY (id)
);

CREATE TABLE fait_remboursement_attendu (
	id SERIAL NOT NULL, 
	date_arrete DATE NOT NULL, 
	date_snapshot DATE NOT NULL, 
	numero_dossier VARCHAR NOT NULL, 
	numero_client VARCHAR, 
	date_echeance DATE, 
	capital_attendu FLOAT, 
	interet FLOAT, 
	capital_restant FLOAT, 
	produit_credit VARCHAR, 
	agent VARCHAR, 
	superviseur VARCHAR, 
	agence VARCHAR, 
	devise VARCHAR, 
	PRIMARY KEY (id)
);

CREATE TABLE fait_remboursement_realise (
	id SERIAL NOT NULL, 
	date_arrete DATE NOT NULL, 
	date_snapshot DATE NOT NULL, 
	numero_dossier VARCHAR NOT NULL, 
	numero_echeance VARCHAR, 
	date_remboursement DATE, 
	numero_client VARCHAR, 
	capital_rembourse FLOAT, 
	interets_rembourses FLOAT, 
	penalites_rembourses FLOAT, 
	devise VARCHAR, 
	PRIMARY KEY (id)
);

CREATE TABLE fait_transaction_caisse (
	id SERIAL NOT NULL, 
	date_arrete DATE NOT NULL, 
	date_snapshot DATE NOT NULL, 
	date_heure TIMESTAMP WITHOUT TIME ZONE, 
	guichet VARCHAR, 
	agent VARCHAR, 
	numero_transaction VARCHAR, 
	libelle_operation VARCHAR, 
	categorie VARCHAR, 
	numero_client VARCHAR, 
	nom_client VARCHAR, 
	montant_debite FLOAT, 
	montant_credite FLOAT, 
	encaisse FLOAT, 
	devise VARCHAR, 
	PRIMARY KEY (id)
);

CREATE TABLE import_log (
	id SERIAL NOT NULL, 
	domaine VARCHAR NOT NULL, 
	fichier VARCHAR NOT NULL, 
	date_snapshot DATE NOT NULL, 
	date_arrete DATE NOT NULL, 
	lignes_acceptees INTEGER, 
	lignes_rejetees INTEGER, 
	horodatage TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	message VARCHAR, 
	PRIMARY KEY (id)
);

CREATE TABLE mapping_budget (
	id SERIAL NOT NULL, 
	numero_compte VARCHAR NOT NULL, 
	ligne_budgetaire VARCHAR NOT NULL, 
	sens VARCHAR, 
	date_effet DATE, 
	PRIMARY KEY (id)
);

CREATE TABLE param_bareme_prime (
	id SERIAL NOT NULL, 
	date_effet DATE NOT NULL, 
	prime_volume FLOAT, 
	prime_nombre FLOAT, 
	prime_couverture FLOAT, 
	seuil_realisation FLOAT, 
	par_min FLOAT, 
	par_max FLOAT, 
	correcteur FLOAT, 
	PRIMARY KEY (id)
);

CREATE TABLE param_bareme_provision (
	id SERIAL NOT NULL, 
	date_effet DATE NOT NULL, 
	min_jours INTEGER, 
	max_jours INTEGER, 
	tranche VARCHAR, 
	taux FLOAT, 
	code INTEGER, 
	PRIMARY KEY (id)
);

CREATE TABLE param_calendrier_ouvre (
	id SERIAL NOT NULL, 
	date DATE NOT NULL, 
	est_ouvre BOOLEAN, 
	libelle VARCHAR, 
	PRIMARY KEY (id), 
	UNIQUE (date)
);

CREATE TABLE param_mapping_compte (
	id SERIAL NOT NULL, 
	date_effet DATE NOT NULL, 
	prefixe VARCHAR NOT NULL, 
	destination VARCHAR, 
	rubrique VARCHAR, 
	type_imf VARCHAR, 
	agregat VARCHAR, 
	PRIMARY KEY (id)
);

CREATE TABLE param_mapping_fina (
	id SERIAL NOT NULL, 
	date_effet DATE NOT NULL, 
	agregat VARCHAR NOT NULL, 
	feuille VARCHAR, 
	code_case VARCHAR, 
	PRIMARY KEY (id)
);

CREATE TABLE param_mapping_libelle (
	id SERIAL NOT NULL, 
	date_effet DATE NOT NULL, 
	libelle VARCHAR NOT NULL, 
	categorie VARCHAR, 
	PRIMARY KEY (id)
);

CREATE TABLE param_norme_bcc (
	id SERIAL NOT NULL, 
	date_effet DATE NOT NULL, 
	indicateur VARCHAR NOT NULL, 
	operateur VARCHAR, 
	seuil_min FLOAT, 
	seuil_max FLOAT, 
	constante FLOAT, 
	PRIMARY KEY (id)
);

CREATE TABLE param_objectif (
	id SERIAL NOT NULL, 
	date_effet DATE NOT NULL, 
	agence VARCHAR, 
	agent VARCHAR, 
	objectif_decaissement_nombre FLOAT, 
	objectif_volume FLOAT, 
	objectif_portefeuille FLOAT, 
	objectif_par FLOAT, 
	PRIMARY KEY (id)
);

CREATE TABLE param_reintegration (
	id SERIAL NOT NULL, 
	date_effet DATE NOT NULL, 
	compte_ou_ligne VARCHAR NOT NULL, 
	taux_reintegration FLOAT, 
	PRIMARY KEY (id)
);

CREATE TABLE param_taux_change (
	id SERIAL NOT NULL, 
	date_effet DATE NOT NULL, 
	devise_source VARCHAR, 
	devise_cible VARCHAR, 
	taux FLOAT NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE param_taux_ibp (
	id SERIAL NOT NULL, 
	date_effet DATE NOT NULL, 
	taux FLOAT, 
	PRIMARY KEY (id)
);

CREATE TABLE provision_manuelle (
	id SERIAL NOT NULL, 
	date_arrete DATE NOT NULL, 
	agence VARCHAR NOT NULL, 
	montant FLOAT NOT NULL, 
	note VARCHAR, 
	saisi_par VARCHAR, 
	horodatage TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_provman_arrete_agence UNIQUE (date_arrete, agence)
);

CREATE TABLE utilisateur (
	id SERIAL NOT NULL, 
	login VARCHAR NOT NULL, 
	nom_complet VARCHAR, 
	mot_de_passe_hash VARCHAR NOT NULL, 
	sel VARCHAR NOT NULL, 
	role VARCHAR NOT NULL, 
	agence VARCHAR, 
	actif BOOLEAN, 
	date_creation DATE, 
	derniere_connexion TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	UNIQUE (login)
);

-- ============================================================
-- ROW LEVEL SECURITY (cloisonnement par agence)
-- ============================================================
-- Principe : un utilisateur AGENCE ne voit que les lignes de son agence.
-- DIRECTION / CDG / AUDIT voient tout.
-- Lier la table utilisateur à auth.users de Supabase (colonne auth_uid à ajouter).

-- Exemple pour fait_credit (à répliquer sur fait_epargne, etc.) :
-- ALTER TABLE fait_credit ENABLE ROW LEVEL SECURITY;
--
-- CREATE POLICY credit_acces_total ON fait_credit
--   FOR SELECT USING (
--     EXISTS (SELECT 1 FROM utilisateur u
--             WHERE u.auth_uid = auth.uid()
--               AND u.role IN ('DIRECTION','CDG','AUDIT'))
--   );
--
-- CREATE POLICY credit_acces_agence ON fait_credit
--   FOR SELECT USING (
--     EXISTS (SELECT 1 FROM utilisateur u
--             WHERE u.auth_uid = auth.uid()
--               AND u.role = 'AGENCE'
--               AND u.agence = fait_credit.agence)
--   );

-- ============================================================
-- INDEX recommandés (performance sur gros volumes)
-- ============================================================
CREATE INDEX IF NOT EXISTS ix_credit_arrete ON fait_credit(date_arrete);
CREATE INDEX IF NOT EXISTS ix_epargne_arrete ON fait_epargne(date_arrete);
CREATE INDEX IF NOT EXISTS ix_balance_arrete ON fait_balance(date_arrete);
CREATE INDEX IF NOT EXISTS ix_credit_agence ON fait_credit(agence);
