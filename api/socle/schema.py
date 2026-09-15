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

from sqlalchemy import (
    Boolean, Column, Date, DateTime, Float, ForeignKey, Integer, String,
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
    """Compte × arrêté. Source balance USD → fichier magique (§38)."""
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
        UniqueConstraint("date_arrete", "numero_compte", name="uq_balance_arrete_compte"),
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
# FABRIQUE
# ─────────────────────────────────────────────────────────────────────────────
import os as _os

def get_engine(db_path: str = "socle/micropop.db"):
    """Connexion à la base.
    - Si la variable d'environnement DATABASE_URL est définie (ex. Supabase PostgreSQL),
      on l'utilise → production.
    - Sinon, repli sur SQLite local (tests, développement hors ligne).
    Aucune donnée n'est perdue : les moteurs métier sont inchangés, seule la cible DB varie.
    """
    url = _os.environ.get("DATABASE_URL")
    if url:
        # normaliser le préfixe pour SQLAlchemy + psycopg (Supabase)
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+psycopg://", 1)
        elif url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+psycopg://", 1)
        return create_engine(url, future=True, pool_pre_ping=True)
    return create_engine(f"sqlite:///{db_path}", future=True)


def init_db(db_path: str = "socle/micropop.db"):
    """Crée les tables. En production (Supabase), le schéma est déjà posé via SQL :
    create_all n'écrase rien (idempotent). Utile surtout en SQLite local."""
    engine = get_engine(db_path)
    Base.metadata.create_all(engine)
    return engine


def get_session(db_path: str = "socle/micropop.db"):
    engine = get_engine(db_path)
    return sessionmaker(bind=engine, future=True)()


if __name__ == "__main__":
    import os
    os.makedirs("socle", exist_ok=True)
    engine = init_db()
    print(f"Base initialisée : {len(Base.metadata.tables)} tables")
    for t in sorted(Base.metadata.tables):
        print(f"  - {t}")
