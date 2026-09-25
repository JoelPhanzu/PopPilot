"""
Socle de données MICROPOP — schéma (Livrable 1 : Modèle de données).

Principes (CLAUDE.md §0.1, §16, §67-69) :
- On stocke des FAITS datés, jamais d'indicateur calculé.
- Deux dates non confondues : date_snapshot (import) et date_arrete (date comptable, fait foi).
- Montants dans la devise d'origine ; conversion dérivée via param_taux_change.
- Paramètres versionnés à date d'effet.

Base : SQLite pour la phase de validation locale (un fichier, zéro serveur).
SQLAlchemy comme ORM → migration PostgreSQL (Phase 6) indolore.
"""
from __future__ import annotations

import datetime

from sqlalchemy import (
    JSON, Boolean, Column, Date, DateTime, Float, ForeignKey, Integer, String, Text, Uuid,
    UniqueConstraint, Index, create_engine,
)
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()


# ─────────────────────────────────────────────────────────────────────────────
# JOURNAL DES IMPORTS (traçabilité — règle I-9)
# ─────────────────────────────────────────────────────────────────────────────
class ImportLog(Base):
    __tablename__ = "import_log"
    id = Column(Integer, primary_key=True)
    domaine = Column(String, nullable=False)            # credit, epargne, balance…
    fichier = Column(String, nullable=False)
    date_snapshot = Column(Date, nullable=False)        # quand la photo est prise
    date_arrete = Column(Date, nullable=False)          # date comptable (fait foi, §69.2)
    lignes_acceptees = Column(Integer, default=0)
    lignes_rejetees = Column(Integer, default=0)
    horodatage = Column(DateTime, nullable=False)
    message = Column(String)


# ─────────────────────────────────────────────────────────────────────────────
# DOMAINE 1 — CRÉDIT
# ─────────────────────────────────────────────────────────────────────────────
class FaitCredit(Base):
    """Un prêt actif × date d'arrêté. Source : extraction SIG colonnes A→AF (§4.1).
    On ne stocke QUE le brut ; provisions/migrations/projections sont recalculées."""
    __tablename__ = "fait_credit"
    id = Column(Integer, primary_key=True)
    date_arrete = Column(Date, nullable=False)          # PK métier composite
    date_snapshot = Column(Date, nullable=False)
    numero_dossier = Column(String, nullable=False)     # CLÉ PIVOT UNIVERSELLE
    numero_client = Column(String)
    nom_client = Column(String)                         # perso → anonymisable en dev
    produit_credit = Column(String)
    est_groupe = Column(Boolean, default=False)         # produit == 'LISANGA' (§45)
    agence = Column(String)
    agent_credit = Column(String)
    superviseur = Column(String)
    id_groupe = Column(String)
    nom_groupe = Column(String)
    sexe = Column(String)
    montant_debourse = Column(Float)
    date_deboursement = Column(Date)
    date_fin_echeance = Column(Date)
    duree = Column(Float)
    taux_interet = Column(Float)
    frequence = Column(String)
    encours = Column(Float)                             # base encours + PAR
    interets = Column(Float)
    interets_retard = Column(Float)
    penalites = Column(Float)
    jours_de_retard = Column(Integer)                   # base PAR + ancienneté
    capital_retard = Column(Float)
    impayes = Column(Float)
    garantie = Column(Float)
    tr_1_7 = Column(Float)
    tr_8_30 = Column(Float)
    tr_31_60 = Column(Float)
    tr_61_90 = Column(Float)
    tr_91_180 = Column(Float)
    tr_181_360 = Column(Float)
    tr_361_plus = Column(Float)
    devise = Column(String, default="USD")
    __table_args__ = (
        UniqueConstraint("date_arrete", "numero_dossier", name="uq_credit_arrete_dossier"),
        Index("ix_credit_arrete", "date_arrete"),
        Index("ix_credit_agence", "agence"),
        Index("ix_credit_agent", "agent_credit"),
    )


class FaitRemboursementAttendu(Base):
    """Échéance due sur une période. Source RBA (§25.1). Contient la hiérarchie."""
    __tablename__ = "fait_remboursement_attendu"
    id = Column(Integer, primary_key=True)
    date_arrete = Column(Date, nullable=False)
    date_snapshot = Column(Date, nullable=False)
    numero_dossier = Column(String, nullable=False)
    numero_client = Column(String)
    date_echeance = Column(Date)
    capital_attendu = Column(Float)
    interet = Column(Float)
    capital_restant = Column(Float)
    produit_credit = Column(String)
    agent = Column(String)
    superviseur = Column(String)
    agence = Column(String)
    devise = Column(String, default="USD")
    __table_args__ = (Index("ix_rba_arrete_dossier", "date_arrete", "numero_dossier"),)


class FaitRemboursementRealise(Base):
    """Ligne d'échéance encaissée. Source CRB (§25.2).
    ⚠️ Lignes « Total » du fichier IGNORÉES à l'import (troncature §25.3)."""
    __tablename__ = "fait_remboursement_realise"
    id = Column(Integer, primary_key=True)
    date_arrete = Column(Date, nullable=False)
    date_snapshot = Column(Date, nullable=False)
    numero_dossier = Column(String, nullable=False)
    numero_echeance = Column(String)
    date_remboursement = Column(Date)
    numero_client = Column(String)
    capital_rembourse = Column(Float)
    interets_rembourses = Column(Float)
    penalites_rembourses = Column(Float)
    devise = Column(String, default="USD")
    __table_args__ = (Index("ix_crb_arrete_dossier", "date_arrete", "numero_dossier"),)


# ─────────────────────────────────────────────────────────────────────────────
# DOMAINE 2 — ÉPARGNE
# ─────────────────────────────────────────────────────────────────────────────
class FaitEpargne(Base):
    """Compte de dépôt × date. Source inventaire dépôt (§51)."""
    __tablename__ = "fait_epargne"
    id = Column(Integer, primary_key=True)
    date_arrete = Column(Date, nullable=False)
    date_snapshot = Column(Date, nullable=False)
    id_compte = Column(String, nullable=False)
    num_complet_cpte = Column(String)
    id_client = Column(String)
    nom_client = Column(String)                         # nom_complet de l'inventaire (SQL 09)
    statut_juridique = Column(String)                   # 1 = PP, 2 = PM, 4 = groupe solidaire (SQL 10)
    id_prod = Column(String)
    libelle_produit = Column(String)
    agence = Column(String)
    devise = Column(String)
    solde_actuel = Column(Float)                        # stock
    solde_debut = Column(Float)
    solde_fin = Column(Float)
    montant_depot = Column(Float)                       # flux
    montant_retrait = Column(Float)
    sexe = Column(String)
    secteur_activite = Column(String)
    ville = Column(String)
    date_ouverture = Column(Date)
    est_groupe = Column(Boolean, default=False)         # 331141 / 33402 (§51.3)
    type_depot = Column(String)                         # a_vue / a_terme / obligatoire (§51.4)
    __table_args__ = (
        Index("ix_epargne_arrete", "date_arrete"),
        Index("ix_epargne_compte", "id_compte"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# DOMAINE 3 — COMPTABILITÉ
# ─────────────────────────────────────────────────────────────────────────────
class FaitBalance(Base):
    """Compte × arrêté × DEVISE. Source balance SAGE (§38).

    LA DEVISE FAIT PARTIE DE LA CLÉ. Deux balances du même arrêté coexistent : la
    balance USD (bilan, indicateurs, budget) et la balance CDF (FINA, §32-37). Sans
    la devise dans la contrainte, importer la balance CDF écrasait la balance USD du
    même arrêté, et le bilan « USD » sortait alors des montants en CDF (facteur ~2268)
    sans le moindre message. Toute lecture doit donc préciser la devise attendue.
    """
    __tablename__ = "fait_balance"
    id = Column(Integer, primary_key=True)
    date_arrete = Column(Date, nullable=False)
    date_snapshot = Column(Date, nullable=False)
    numero_compte = Column(String, nullable=False)
    libelle = Column(String)
    debit_initial = Column(Float)
    credit_initial = Column(Float)
    debit_mvmt = Column(Float)
    credit_mvmt = Column(Float)
    solde_net = Column(Float)                           # devise d'origine
    devise = Column(String, default="USD")
    __table_args__ = (
        UniqueConstraint("date_arrete", "numero_compte", "devise",
                         name="uq_balance_arrete_compte_devise"),
        Index("ix_balance_arrete", "date_arrete"),
    )


class FaitGrandLivre(Base):
    """Une écriture. Source GL (§55, §62)."""
    __tablename__ = "fait_grand_livre"
    id = Column(Integer, primary_key=True)
    date_arrete = Column(Date, nullable=False)
    date_snapshot = Column(Date, nullable=False)
    date_ecriture = Column(Date)
    numero_compte = Column(String, nullable=False)
    ligne_budgetaire = Column(String)
    mois = Column(String)
    libelle = Column(String)
    devise = Column(String)
    montant = Column(Float)
    __table_args__ = (Index("ix_gl_arrete_compte", "date_arrete", "numero_compte"),)


# ─────────────────────────────────────────────────────────────────────────────
# DOMAINE 4 — TRANSACTIONS / TRÉSORERIE
# ─────────────────────────────────────────────────────────────────────────────
class FaitTransactionCaisse(Base):
    """Une opération de caisse. Source brouillard USD+CDF (§54)."""
    __tablename__ = "fait_transaction_caisse"
    id = Column(Integer, primary_key=True)
    date_arrete = Column(Date, nullable=False)
    date_snapshot = Column(Date, nullable=False)
    date_heure = Column(DateTime)
    guichet = Column(String)
    agent = Column(String)
    numero_transaction = Column(String)
    libelle_operation = Column(String)
    categorie = Column(String)                          # dérivé via param_mapping_libelle (§54.1)
    numero_client = Column(String)
    nom_client = Column(String)
    montant_debite = Column(Float)
    montant_credite = Column(Float)
    encaisse = Column(Float)
    devise = Column(String)
    __table_args__ = (Index("ix_tx_arrete", "date_arrete"),)


# ─────────────────────────────────────────────────────────────────────────────
# DOMAINE 5 — BUDGET (saisie humaine, versionné)
# ─────────────────────────────────────────────────────────────────────────────
class FaitBudget(Base):
    """Ligne budgétaire × agence × mois × hypothèse. Source budget (§46). Saisie/versionné."""
    __tablename__ = "fait_budget"
    id = Column(Integer, primary_key=True)
    exercice = Column(Integer, nullable=False)
    hypothese = Column(String, default="H1")
    agence = Column(String)
    ligne_budgetaire = Column(String)
    produit = Column(String)
    mois = Column(Integer)
    montant_budgete = Column(Float)
    type = Column(String)                               # encours/produit/charge/effectif/PAR_cible
    __table_args__ = (Index("ix_budget_ex_hyp", "exercice", "hypothese"),)


# ─────────────────────────────────────────────────────────────────────────────
# DOMAINE 6 — RÉMUNÉRATION
# ─────────────────────────────────────────────────────────────────────────────
class FaitPrime(Base):
    """Employé × période. Dérivé des KPI + barème (§60)."""
    __tablename__ = "fait_prime"
    id = Column(Integer, primary_key=True)
    periode = Column(Date, nullable=False)
    employe = Column(String, nullable=False)
    fonction = Column(String)
    agence = Column(String)
    base_volume = Column(Float)
    base_nombre = Column(Float)
    base_couverture = Column(Float)
    par_agent = Column(Float)
    correcteur_par = Column(Float)
    prime_calculee = Column(Float)


# ─────────────────────────────────────────────────────────────────────────────
# DIMENSIONS (référentiels) — avec date d'effet quand versionnées
# ─────────────────────────────────────────────────────────────────────────────
class DimAgence(Base):
    __tablename__ = "dim_agence"
    id = Column(Integer, primary_key=True)
    code_agence = Column(String, unique=True, nullable=False)
    nom = Column(String)
    region = Column(String)
    date_ouverture = Column(Date)
    statut = Column(String, default="ACTIVE")           # ACTIVE / FERMEE / SUSPENDUE (§ note métier)
    date_fermeture = Column(Date)                        # NULL si active
    motif = Column(String)                               # ex. "Occupation M23"


class DimEmploye(Base):
    """Roster (Composition Equipe §5). date_debut/date_fin → historisation du roster (§18.4)."""
    __tablename__ = "dim_employe"
    id = Column(Integer, primary_key=True)
    nom = Column(String, nullable=False)
    fonction = Column(String)                           # agent_credit / superviseur / …
    agence = Column(String)
    date_debut = Column(Date)
    date_fin = Column(Date)                             # NULL = encore en poste
    __table_args__ = (Index("ix_employe_nom", "nom"),)


class DimProduitCredit(Base):
    __tablename__ = "dim_produit_credit"
    id = Column(Integer, primary_key=True)
    produit = Column(String, unique=True, nullable=False)
    est_groupe = Column(Boolean, default=False)
    secteur = Column(String)                            # Commerce/Agricole/Services/Autres (F10)


class DimProduitEpargne(Base):
    __tablename__ = "dim_produit_epargne"
    id = Column(Integer, primary_key=True)
    id_prod = Column(String, unique=True, nullable=False)
    libelle = Column(String)
    type_depot = Column(String)                         # a_vue / a_terme / obligatoire
    est_groupe = Column(Boolean, default=False)
    compte_bcc = Column(String)


class DimPlanComptable(Base):
    __tablename__ = "dim_plan_comptable"
    id = Column(Integer, primary_key=True)
    numero = Column(String, unique=True, nullable=False)
    libelle = Column(String)
    prefixe = Column(String)
    agregat = Column(String)


class DimClient(Base):
    __tablename__ = "dim_client"
    id = Column(Integer, primary_key=True)
    numero_client = Column(String, unique=True, nullable=False)
    nom = Column(String)
    sexe = Column(String)
    secteur = Column(String)
    ville = Column(String)
    statut_juridique = Column(String)


# ─────────────────────────────────────────────────────────────────────────────
# PARAMÈTRES (versionnés à date d'effet — §18.4)
# Table générique à date d'effet : chaque paramètre a une date à partir de laquelle il vaut.
# ─────────────────────────────────────────────────────────────────────────────
class ParamBaremeProvision(Base):
    """Tranche d'ancienneté → taux → code (§4.4). Versionné."""
    __tablename__ = "param_bareme_provision"
    id = Column(Integer, primary_key=True)
    date_effet = Column(Date, nullable=False)
    min_jours = Column(Integer)
    max_jours = Column(Integer)                         # NULL = illimité
    tranche = Column(String)
    taux = Column(Float)                                # 0/0.05/0.25/0.5/0.75/1.0
    code = Column(Integer)                              # 0..6


class ParamObjectif(Base):
    """Objectifs agence/agent × période (§15.3). Versionné."""
    __tablename__ = "param_objectif"
    id = Column(Integer, primary_key=True)
    date_effet = Column(Date, nullable=False)
    agence = Column(String)
    agent = Column(String)
    objectif_decaissement_nombre = Column(Float)
    objectif_volume = Column(Float)
    objectif_portefeuille = Column(Float)
    objectif_par = Column(Float)                        # cible-seuil (jamais proratisée §24.2)


class ParamTauxChange(Base):
    """Date → taux de clôture USD→CDF (§42)."""
    __tablename__ = "param_taux_change"
    id = Column(Integer, primary_key=True)
    date_effet = Column(Date, nullable=False)
    devise_source = Column(String, default="USD")
    devise_cible = Column(String, default="CDF")
    taux = Column(Float, nullable=False)


class ParamBaremePrime(Base):
    """Barème primes + correcteur PAR (§60). Versionné."""
    __tablename__ = "param_bareme_prime"
    id = Column(Integer, primary_key=True)
    date_effet = Column(Date, nullable=False)
    prime_volume = Column(Float)
    prime_nombre = Column(Float)
    prime_couverture = Column(Float)
    seuil_realisation = Column(Float)
    par_min = Column(Float)                             # borne basse tranche PAR
    par_max = Column(Float)
    correcteur = Column(Float)                          # multiplicateur ×1/0.7/0.5/0


class ParamMappingCompte(Base):
    """Préfixe/compte → agrégat (§40)."""
    __tablename__ = "param_mapping_compte"
    id = Column(Integer, primary_key=True)
    date_effet = Column(Date, nullable=False)
    prefixe = Column(String, nullable=False)
    destination = Column(String)                        # ACTIF/PASSIF/RESULTAT/ACTIF-PASSIF
    rubrique = Column(String)
    type_imf = Column(String)
    agregat = Column(String)


class ParamMappingLibelle(Base):
    """Libellé opération → catégorie (§54.1)."""
    __tablename__ = "param_mapping_libelle"
    id = Column(Integer, primary_key=True)
    date_effet = Column(Date, nullable=False)
    libelle = Column(String, nullable=False)
    categorie = Column(String)                          # depot_espece / retrait / transfert…


class ParamNormeBCC(Base):
    """Indicateur → norme/seuil/constante (§28)."""
    __tablename__ = "param_norme_bcc"
    id = Column(Integer, primary_key=True)
    date_effet = Column(Date, nullable=False)
    indicateur = Column(String, nullable=False)
    operateur = Column(String)                          # <, >, >=, <=, entre
    seuil_min = Column(Float)
    seuil_max = Column(Float)
    constante = Column(Float)                           # ex. capital min 700 000 USD


class ParamReintegration(Base):
    """Nature de charge → taux de réintégration fiscale (§67)."""
    __tablename__ = "param_reintegration"
    id = Column(Integer, primary_key=True)
    date_effet = Column(Date, nullable=False)
    compte_ou_ligne = Column(String, nullable=False)   # ex. communication, dons_personnel
    taux_reintegration = Column(Float)                  # 0.5, 1.0…


class ParamTauxIBP(Base):
    """Taux légal IBP appliqué au résultat fiscal (§67)."""
    __tablename__ = "param_taux_ibp"
    id = Column(Integer, primary_key=True)
    date_effet = Column(Date, nullable=False)
    taux = Column(Float, default=0.30)


class ParamCalendrierOuvre(Base):
    """Jours non ouvrés (fériés RDC + exceptions) → prorata & dernier jour ouvré (§69)."""
    __tablename__ = "param_calendrier_ouvre"
    id = Column(Integer, primary_key=True)
    date = Column(Date, unique=True, nullable=False)
    est_ouvre = Column(Boolean, default=False)          # False = férié/non ouvré
    libelle = Column(String)


class Utilisateur(Base):
    """Utilisateur de la plateforme : login, mot de passe (haché), rôle, agence.
    Rôles : DIRECTION (tout), CDG (tout), AGENCE (cloisonné à son agence), AUDIT (lecture)."""
    __tablename__ = "utilisateur"
    id = Column(Integer, primary_key=True)
    login = Column(String, unique=True, nullable=False)
    nom_complet = Column(String)
    mot_de_passe_hash = Column(String, nullable=False)   # sha256(sel + mdp)
    sel = Column(String, nullable=False)
    role = Column(String, nullable=False)                # DIRECTION / CDG / AGENCE / AUDIT
    agence = Column(String)                              # NULL sauf pour role AGENCE
    actif = Column(Boolean, default=True)
    date_creation = Column(Date)
    derniere_connexion = Column(DateTime)
    # Lien vers le compte Supabase (auth.users.id). Pose par supabase/02_auth_rls.sql.
    # C'est la cle utilisee par api/auth_supabase.py pour identifier l'appelant a
    # partir du "sub" de son jeton JWT. Uuid() -> uuid natif sur PostgreSQL,
    # CHAR(32) sur le repli SQLite local.
    # UNIQUE : deux lignes portant le meme auth_uid rendraient pp_role() non
    # deterministe (SELECT ... LIMIT 1 sans ORDER BY cote base) -> le role retenu
    # serait tire au hasard, y compris un DIRECTION face a un AGENCE. Faille
    # silencieuse : on l'interdit au niveau du schema.
    auth_uid = Column(Uuid(as_uuid=False), unique=True, index=True)


class MappingBudget(Base):
    """Correspondance compte comptable -> ligne budgétaire (ÉDITABLE, dynamique).
    Permet nouvelles affectations et réaffectations sans toucher au code (§budget)."""
    __tablename__ = "mapping_budget"
    id = Column(Integer, primary_key=True)
    numero_compte = Column(String, nullable=False)      # format budget "6.0.2.0.1"
    ligne_budgetaire = Column(String, nullable=False)
    sens = Column(String)                               # "charge" / "produit"
    date_effet = Column(Date)                           # versionné (réorganisations)


class ProvisionManuelle(Base):
    """Provision saisie MANUELLEMENT par agence pour un arrêté (décision comptable + DAF).
    Remplace le barème automatique pour l'agence concernée (ex. Goma, agence fermée, 1 % cumulé).
    Traçable : montant, note, qui/quand."""
    __tablename__ = "provision_manuelle"
    id = Column(Integer, primary_key=True)
    date_arrete = Column(Date, nullable=False)
    agence = Column(String, nullable=False)
    montant = Column(Float, nullable=False)             # provision capital retenue pour l'agence
    note = Column(String)                                # ex. "16 % — 1 % cumulé, validé DAF"
    saisi_par = Column(String)
    horodatage = Column(DateTime)
    __table_args__ = (
        UniqueConstraint("date_arrete", "agence", name="uq_provman_arrete_agence"),
    )


class ParamMappingFina(Base):
    """Compte/agrégat → case FINA V1.F… (§37)."""
    __tablename__ = "param_mapping_fina"
    id = Column(Integer, primary_key=True)
    date_effet = Column(Date, nullable=False)
    agregat = Column(String, nullable=False)
    feuille = Column(String)
    code_case = Column(String)                          # V1.F0a.xx


# ─────────────────────────────────────────────────────────────────────────────
# AMÉLIORATIONS (chantiers 1-7) — tables créées par supabase/06 et 07.
# Déclarées ici À L'IDENTIQUE du SQL pour que le code les lise et les écrive. En
# production, create_all ne les recrée pas (elles existent : IF NOT EXISTS côté SQL,
# checkfirst côté SQLAlchemy). En SQLite (tests), create_all les crée.
# ─────────────────────────────────────────────────────────────────────────────
class CompteResultatAgence(Base):
    """Compte de résultat isolé par agence (fichier mensuel du CDG) — poste × agence × mois."""
    __tablename__ = "compte_resultat_agence"
    id = Column(Integer, primary_key=True)
    date_arrete = Column(Date, nullable=False)
    poste = Column(String, nullable=False)
    agence = Column(String, nullable=False)
    montant = Column(Float)
    devise = Column(String, default="USD")
    __table_args__ = (UniqueConstraint("date_arrete", "poste", "agence", name="uq_cra"),)


class FaitCollecteEpargne(Base):
    """Collecte d'épargne du mois par agence (fichier Agence | Cible | Réalisation) — base de la
    prime des superviseurs épargne. Daté : date_arrete = dernier jour du mois concerné."""
    __tablename__ = "fait_collecte_epargne"
    id = Column(Integer, primary_key=True)
    date_arrete = Column(Date, nullable=False)
    agence = Column(String, nullable=False)
    cible = Column(Float)
    realisation = Column(Float)
    fichier = Column(String)
    importe_par = Column(String)
    horodatage = Column(DateTime, default=datetime.datetime.now)
    __table_args__ = (UniqueConstraint("date_arrete", "agence", name="uq_collecte_epargne"),)


class FaitRemboursementEncaisse(Base):
    """Remboursements encaissés, hiérarchie (agent/superviseur/agence) résolue à l'import."""
    __tablename__ = "fait_remboursement_encaisse"
    id = Column(Integer, primary_key=True)
    date_arrete = Column(Date, nullable=False)
    date_remboursement = Column(Date)
    numero_dossier = Column(String, nullable=False)
    numero_client = Column(String)
    numero_echeance = Column(String)
    capital_rembourse = Column(Float)
    interets_rembourses = Column(Float)
    penalites_rembourses = Column(Float)
    agent_credit = Column(String)
    superviseur = Column(String)
    agence = Column(String)


class JournalSageTraite(Base):
    """Trace de chaque traitement du grand livre CBS pour SAGE."""
    __tablename__ = "journal_sage_traite"
    id = Column(Integer, primary_key=True)
    date_traitement = Column(Date, nullable=False)
    periode = Column(String)
    fichier_source = Column(String)
    lignes_entree = Column(Integer)
    lignes_sortie = Column(Integer)
    statut = Column(String)                  # OK / ALERTE / ECHEC
    message = Column(String)


class CampagnePrime(Base):
    """Paramètres de prime appliqués à une période (snapshot figé, traçabilité)."""
    __tablename__ = "campagne_prime"
    id = Column(Integer, primary_key=True)
    periode = Column(Date, nullable=False, unique=True)
    date_calcul = Column(Date)
    parametres = Column(JSON)                # JSONB côté Supabase
    valide_par = Column(String)


class EljoConversation(Base):
    """Eljo Smart : chaque question et la réponse donnée (valeur exacte du moteur)."""
    __tablename__ = "eljo_conversation"
    id = Column(Integer, primary_key=True)
    auth_uid = Column(Uuid)
    login = Column(String)
    role = Column(String)
    agence = Column(String)
    question = Column(Text, nullable=False)
    intention = Column(String)
    reponse = Column(Text)
    valeur = Column(Float)
    horodatage = Column(DateTime, default=datetime.datetime.now)


class ArchiveRapport(Base):
    """Bibliothèque de rapports, remplaçables (version + remplace_id = historique)."""
    __tablename__ = "archive_rapport"
    id = Column(Integer, primary_key=True)
    titre = Column(String, nullable=False)
    type_rapport = Column(String)
    periode = Column(String)
    fichier_url = Column(String)
    format = Column(String)
    version = Column(Integer, default=1)
    depose_par = Column(String)
    date_depot = Column(DateTime, default=datetime.datetime.now)
    remplace_id = Column(Integer)


class SerieIndicateur(Base):
    """Séries temporelles d'indicateurs (historiques importés + calculs mensuels)."""
    __tablename__ = "serie_indicateur"
    id = Column(Integer, primary_key=True)
    indicateur = Column(String, nullable=False)
    date_arrete = Column(Date, nullable=False)
    agence = Column(String)                  # NULL = consolidé
    valeur = Column(Float)
    unite = Column(String)
    source = Column(String)


class ArchiveDonnees(Base):
    """Données d'une archive éditables en ligne, cellule par cellule (modif tracée)."""
    __tablename__ = "archive_donnees"
    id = Column(Integer, primary_key=True)
    archive_id = Column(Integer, ForeignKey("archive_rapport.id"))
    ligne = Column(Integer, nullable=False)
    colonne = Column(String, nullable=False)
    valeur = Column(Text)
    modifie_par = Column(String)
    modifie_le = Column(DateTime, default=datetime.datetime.now)


# ─────────────────────────────────────────────────────────────────────────────
# FABRIQUE
# ─────────────────────────────────────────────────────────────────────────────
import os as _os
from pathlib import Path as _Path


def _charger_env():
    """Charge api/.env (DATABASE_URL, SUPABASE_JWT_SECRET) s'il existe.

    POURQUOI : sans cela, DATABASE_URL reste vide et TOUTE la plateforme bascule
    silencieusement sur le repli SQLite local (base vide) -> les rapports sortiraient
    des chiffres faux sans le moindre message. Le .env est ignore par git (.gitignore).
    Les variables deja presentes dans l'environnement gagnent (override=False).
    """
    env = _Path(__file__).resolve().parent.parent / ".env"   # api/.env
    if not env.exists():
        return
    try:
        from dotenv import load_dotenv
        load_dotenv(env, override=False)
    except ImportError:                      # repli sans python-dotenv
        for ligne in env.read_text(encoding="utf-8").splitlines():
            ligne = ligne.strip()
            if not ligne or ligne.startswith("#") or "=" not in ligne:
                continue
            cle, _, val = ligne.partition("=")
            _os.environ.setdefault(cle.strip(), val.strip().strip('"').strip("'"))


_charger_env()


# Marqueurs du fichier .env.example : s'ils sont encore la, le .env n'a pas ete rempli.
_GABARITS = ("[MOT_DE_PASSE]", "[TON_JWT_SECRET_SUPABASE]", "<MOT_DE_PASSE>")


def env_encore_gabarit() -> str | None:
    """Renvoie un message si api/.env contient encore les valeurs a remplacer.

    Sans ce controle, une URL restee au gabarit produit une erreur DNS incomprehensible
    (« failed to resolve host ») au lieu de dire simplement : le .env n'est pas rempli.
    """
    for cle in ("DATABASE_URL", "SUPABASE_JWT_SECRET"):
        valeur = _os.environ.get(cle) or ""
        for marqueur in _GABARITS:
            if marqueur in valeur:
                return (f"{cle} contient encore {marqueur} : api/.env n'a pas ete complete "
                        "(Supabase > Project Settings > Database / API).")
    return None


def cible_base() -> str:
    """Decrit la base visee, SANS jamais exposer le mot de passe (pour les logs)."""
    url = _os.environ.get("DATABASE_URL")
    if not url:
        return "SQLite local (repli) - DATABASE_URL non definie"
    if any(m in url for m in _GABARITS):
        return "api/.env NON COMPLETE (valeurs du gabarit encore presentes)"
    hote = url.split("@")[-1].split("/")[0] if "@" in url else "?"
    return f"PostgreSQL/Supabase ({hote})"


BASE_PAR_DEFAUT = "socle/micropop.db"


def _url_cible(db_path: str) -> str:
    """URL SQLAlchemy visée.

    RÈGLE DE SÉCURITÉ — quelle base pour quel appel :
      - db_path laissé au défaut (« la base de la plateforme ») → Supabase si
        DATABASE_URL est définie, sinon SQLite local. C'est le cas de l'API et des
        moteurs appelés sans préciser de base.
      - db_path EXPLICITE et différent du défaut (ex. « socle/test_phase1.db ») →
        TOUJOURS ce fichier SQLite, jamais Supabase.

    POURQUOI : sans cette distinction, DATABASE_URL écrasait le db_path des tests.
    Résultat : dès que api/.env pointait sur la production, lancer la campagne de
    validation importait les jeux de test DANS LA BASE SUPABASE DE PRODUCTION
    (importer_credit purge puis réécrit une date d'arrêté). Une base nommée
    explicitement doit rester locale.
    """
    if db_path and db_path != BASE_PAR_DEFAUT:
        return f"sqlite:///{db_path}"
    url = _os.environ.get("DATABASE_URL")
    if not url:
        return f"sqlite:///{db_path}"
    # normaliser le préfixe pour SQLAlchemy + psycopg (Supabase)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


# Un moteur SQLAlchemy porte un POOL de connexions. En créer un par appel ouvrirait
# un nouveau pool à CHAQUE requête de l'API (auth_supabase appelle get_session à chaque
# fois) → épuisement des connexions PostgreSQL de Supabase sous charge. On les met donc
# en cache par URL cible. Clé = l'URL, pas le db_path : ainsi un basculement de
# DATABASE_URL (tests) donne bien un moteur distinct.
_moteurs: dict[str, object] = {}


def get_engine(db_path: str = BASE_PAR_DEFAUT):
    """Connexion à la base (moteur mis en cache, un seul pool par cible).
    - DATABASE_URL définie (ex. Supabase PostgreSQL) → production.
    - Sinon, repli sur SQLite local (tests, développement hors ligne).
    Les moteurs métier sont inchangés : seule la cible DB varie.
    """
    url = _url_cible(db_path)
    moteur = _moteurs.get(url)
    if moteur is None:
        if url.startswith("sqlite"):
            moteur = create_engine(url, future=True)
        else:
            # pool_pre_ping : Supabase ferme les connexions inactives ; on vérifie
            # qu'une connexion recyclée est encore vivante avant de s'en servir.
            moteur = create_engine(url, future=True, pool_pre_ping=True,
                                   pool_size=5, max_overflow=5, pool_recycle=1800)
        _moteurs[url] = moteur
    return moteur


def fermer_moteurs() -> None:
    """Ferme tous les pools et vide le cache.

    Indispensable aux tests sous Windows : tant qu'un moteur SQLite garde le fichier
    ouvert, os.remove() lève PermissionError (WinError 32) et le test s'interrompt.
    """
    for moteur in _moteurs.values():
        try:
            moteur.dispose()
        except Exception:
            pass
    _moteurs.clear()


def init_db(db_path: str = BASE_PAR_DEFAUT):
    """Crée les tables. En production (Supabase), le schéma est déjà posé via SQL :
    create_all n'écrase rien (idempotent). Utile surtout en SQLite local."""
    engine = get_engine(db_path)
    Base.metadata.create_all(engine)
    return engine


def get_session(db_path: str = BASE_PAR_DEFAUT):
    engine = get_engine(db_path)
    return sessionmaker(bind=engine, future=True)()


if __name__ == "__main__":
    import os
    os.makedirs("socle", exist_ok=True)
    engine = init_db()
    print(f"Base initialisée : {len(Base.metadata.tables)} tables")
    for t in sorted(Base.metadata.tables):
        print(f"  - {t}")
