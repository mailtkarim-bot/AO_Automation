"""Modèles ORM du schéma Batião.

Architecture :
  - TENANT (entreprise cliente) isole toutes les données d'un client.
  - PROJET (1 appel d'offres) contient la documentation et les 3 enveloppes.
  - DOCUMENTS bruts uploadés → CHUNKS (RAG) → EXTRACTIONS structurées de l'IA.
  - L'enveloppe financière est isolée des autres (règle d'indépendance).

Toutes les tables portent tenant_id ou projet_id pour garantir l'isolation.
"""
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


# ---------- Mixins ----------
class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


# ---------- Tenants & utilisateurs ----------
class Tenant(Base, TimestampMixin):
    __tablename__ = "tenants"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    nom: Mapped[str] = mapped_column(String(255), nullable=False)
    siret: Mapped[str | None] = mapped_column(String(20))

    users: Mapped[list["User"]] = relationship(back_populates="tenant")
    projets: Mapped[list["Projet"]] = relationship(back_populates="tenant")
    biblio_memoires: Mapped[list["BiblioMemoire"]] = relationship(back_populates="tenant")
    biblio_bpu: Mapped[list["BiblioBpu"]] = relationship(back_populates="tenant")
    biblio_attestations: Mapped[list["BiblioAttestation"]] = relationship(back_populates="tenant")


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    nom_complet: Mapped[str | None] = mapped_column(String(255))
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(50), default="user")  # admin | user

    tenant: Mapped[Tenant] = relationship(back_populates="users")


# ---------- Bibliothèque d'entreprise (réutilisable entre projets) ----------
class BiblioMemoire(Base, TimestampMixin):
    """Mémoires techniques modèles fournis par l'entreprise (carburant du RAG)."""
    __tablename__ = "biblio_memoires"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    titre: Mapped[str] = mapped_column(String(500))
    corps: Mapped[str] = mapped_column(Text)
    metadonnees: Mapped[dict] = mapped_column(JSONB, default=dict)

    tenant: Mapped[Tenant] = relationship(back_populates="biblio_memoires")


class BiblioBpu(Base, TimestampMixin):
    """BPU (bordereau de prix unitaire) de référence de l'entreprise."""
    __tablename__ = "biblio_bpu"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    ouvrage: Mapped[str] = mapped_column(String(500), nullable=False)
    unite: Mapped[str] = mapped_column(String(20), nullable=False)
    prix_ht: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    date_validite: Mapped[date | None] = mapped_column(Date)
    metadonnees: Mapped[dict] = mapped_column(JSONB, default=dict)

    tenant: Mapped[Tenant] = relationship(back_populates="biblio_bpu")


class BiblioAttestation(Base, TimestampMixin):
    """Attestations administratives réutilisables (DC1, URSSAF, MSA, CNETP...)."""
    __tablename__ = "biblio_attestations"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String(50), index=True)  # DC1 | URSSAF | MSA | CNETP | ...
    nom_fichier: Mapped[str] = mapped_column(String(500))
    chemin_stockage: Mapped[str] = mapped_column(String(1000))
    expire_le: Mapped[date | None] = mapped_column(Date, index=True)

    tenant: Mapped[Tenant] = relationship(back_populates="biblio_attestations")


# ---------- PROJET = 1 appel d'offres ----------
class Projet(Base, TimestampMixin):
    __tablename__ = "projets"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)

    intitule: Mapped[str] = mapped_column(String(1000), nullable=False)
    maitre_ouvrage: Mapped[str | None] = mapped_column(String(500))
    lieu: Mapped[str | None] = mapped_column(String(500))
    montant_estime: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    procedure: Mapped[str | None] = mapped_column(String(50))  # MAPA | FORMALISEE | ...
    ccag: Mapped[str | None] = mapped_column(String(100))      # ex. "CCAG-Travaux 2021"
    date_remise: Mapped[date | None] = mapped_column(Date, index=True)
    statut: Mapped[str] = mapped_column(String(50), default="cree", index=True)
    # cree | en_analyse | go | no_go | en_reponse | remis | perdu | gagne

    metadonnees: Mapped[dict] = mapped_column(JSONB, default=dict)

    tenant: Mapped[Tenant] = relationship(back_populates="projets")
    documents: Mapped[list["Document"]] = relationship(
        back_populates="projet", cascade="all, delete-orphan"
    )
    chunks: Mapped[list["DocumentChunk"]] = relationship(
        back_populates="projet", cascade="all, delete-orphan"
    )
    analyse_go_nogo: Mapped[list["AnalyseGoNoGo"]] = relationship(back_populates="projet")
    criteres: Mapped[list["CritereSelection"]] = relationship(back_populates="projet")
    ouvrages: Mapped[list["OuvrageCctp"]] = relationship(back_populates="projet")
    clauses: Mapped[list["ClauseSensible"]] = relationship(back_populates="projet")
    echeances: Mapped[list["Echeance"]] = relationship(back_populates="projet")
    env_admin: Mapped["EnveloppeAdministrative | None"] = relationship(back_populates="projet")
    env_technique: Mapped["EnveloppeTechnique | None"] = relationship(back_populates="projet")
    env_financiere: Mapped["EnveloppeFinanciere | None"] = relationship(back_populates="projet")


# ---------- Documents bruts ----------
DOC_TYPES = ("CCTP", "CCAP", "RC", "AAPC", "RCAP", "BPU", "DPGF", "PA", "CCAG", "AE", "AUTRE")
DOC_STATUS = ("EN_ATTENTE", "EN_COURS", "PARSE_OK", "ERREUR", "VECTORIZED")


class Document(Base, TimestampMixin):
    __tablename__ = "documents"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    projet_id: Mapped[UUID] = mapped_column(ForeignKey("projets.id", ondelete="CASCADE"), index=True)

    type: Mapped[str] = mapped_column(String(20), index=True)  # voir DOC_TYPES
    nom_fichier: Mapped[str] = mapped_column(String(500), nullable=False)
    chemin_stockage: Mapped[str] = mapped_column(String(1000), nullable=False)
    hash: Mapped[str] = mapped_column(String(64), index=True)     # sha256
    taille_octets: Mapped[int] = mapped_column(BigInteger, default=0)
    mime_type: Mapped[str | None] = mapped_column(String(100))

    statut: Mapped[str] = mapped_column(String(20), default="EN_ATTENTE", index=True)
    nb_pages: Mapped[int | None] = mapped_column(Integer)
    texte_complet: Mapped[str | None] = mapped_column(Text)       # brut, pour debug
    erreur: Mapped[str | None] = mapped_column(Text)
    parsed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    vectorized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    projet: Mapped[Projet] = relationship(back_populates="documents")
    chunks: Mapped[list["DocumentChunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class DocumentChunk(Base):
    """Découpage sémantique d'un document pour le RAG.

    L'embedding vit dans une « collection logique » = (projet_id, enveloppe).
    Pour l'enveloppe financière, on tagge `enveloppe='FINANCIERE'` afin de
    ne jamais la croiser avec le technique (règle d'indépendance).
    """
    __tablename__ = "document_chunks"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    projet_id: Mapped[UUID] = mapped_column(ForeignKey("projets.id", ondelete="CASCADE"), index=True)
    enveloppe: Mapped[str] = mapped_column(String(20), default="GEN", index=True)
    # GEN | ADMIN | TECHNIQUE | FINANCIERE

    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    texte: Mapped[str] = mapped_column(Text, nullable=False)
    page_source: Mapped[int | None] = mapped_column(Integer)
    section: Mapped[str | None] = mapped_column(String(500))
    # Dimension 1024 = embeddings Mistral (mistral-embed)
    embedding: Mapped[list[float]] = mapped_column(Vector(1024))

    document: Mapped[Document] = relationship(back_populates="chunks")
    projet: Mapped[Projet] = relationship(back_populates="chunks")


# ---------- Extractions IA (sorties structurées) ----------
class AnalyseGoNoGo(Base, TimestampMixin):
    __tablename__ = "analyses_go_nogo"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    projet_id: Mapped[UUID] = mapped_column(ForeignKey("projets.id", ondelete="CASCADE"), index=True)

    verdict: Mapped[str] = mapped_column(String(20), index=True)  # JOUER | RISQUE | EVITER
    score: Mapped[int] = mapped_column(Integer)                   # 0-100
    synthese: Mapped[str] = mapped_column(Text)
    red_flags: Mapped[list] = mapped_column(JSONB, default=list)  # liste d'objets
    points_forts: Mapped[list] = mapped_column(JSONB, default=list)
    detail: Mapped[dict] = mapped_column(JSONB, default=dict)
    model_used: Mapped[str | None] = mapped_column(String(100))
    prompt_version: Mapped[str | None] = mapped_column(String(50))

    projet: Mapped[Projet] = relationship(back_populates="analyse_go_nogo")


class CritereSelection(Base, TimestampMixin):
    __tablename__ = "criteres_selection"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    projet_id: Mapped[UUID] = mapped_column(ForeignKey("projets.id", ondelete="CASCADE"), index=True)

    critere: Mapped[str] = mapped_column(String(500), nullable=False)
    ponderation: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    sous_criteres: Mapped[list] = mapped_column(JSONB, default=list)
    source_doc_id: Mapped[UUID | None] = mapped_column(ForeignKey("documents.id"))

    projet: Mapped[Projet] = relationship(back_populates="criteres")


class OuvrageCctp(Base, TimestampMixin):
    __tablename__ = "ouvrages_cctp"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    projet_id: Mapped[UUID] = mapped_column(ForeignKey("projets.id", ondelete="CASCADE"), index=True)

    lot: Mapped[str | None] = mapped_column(String(200), index=True)
    designation: Mapped[str] = mapped_column(Text, nullable=False)
    unite: Mapped[str | None] = mapped_column(String(20))
    quantite: Mapped[Decimal | None] = mapped_column(Numeric(14, 3))
    description: Mapped[str | None] = mapped_column(Text)
    source_doc_id: Mapped[UUID | None] = mapped_column(ForeignKey("documents.id"))

    projet: Mapped[Projet] = relationship(back_populates="ouvrages")


class ClauseSensible(Base, TimestampMixin):
    __tablename__ = "clauses_sensibles"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    projet_id: Mapped[UUID] = mapped_column(ForeignKey("projets.id", ondelete="CASCADE"), index=True)

    type: Mapped[str] = mapped_column(String(50), index=True)
    # PENALITE | GARANTIE | CCAG | DELAI | REDEVANCE | RESERVE | ...
    libelle: Mapped[str] = mapped_column(Text, nullable=False)
    severite: Mapped[str] = mapped_column(String(20), default="INFO")
    # INFO | ATTENTION | CRITIQUE
    source_doc_id: Mapped[UUID | None] = mapped_column(ForeignKey("documents.id"))
    page_source: Mapped[int | None] = mapped_column(Integer)
    detail: Mapped[dict] = mapped_column(JSONB, default=dict)

    projet: Mapped[Projet] = relationship(back_populates="clauses")


class Echeance(Base, TimestampMixin):
    __tablename__ = "echeances"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    projet_id: Mapped[UUID] = mapped_column(ForeignKey("projets.id", ondelete="CASCADE"), index=True)

    type: Mapped[str] = mapped_column(String(50))  # REMISE | VISITE | QUESTION | ...
    date: Mapped[date] = mapped_column(Date, index=True)
    commentaire: Mapped[str | None] = mapped_column(Text)
    source_doc_id: Mapped[UUID | None] = mapped_column(ForeignKey("documents.id"))

    projet: Mapped[Projet] = relationship(back_populates="echeances")


# ---------- Les 3 enveloppes ----------
class EnveloppeAdministrative(Base, TimestampMixin):
    __tablename__ = "enveloppe_administrative"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    projet_id: Mapped[UUID] = mapped_column(
        ForeignKey("projets.id", ondelete="CASCADE"), unique=True, index=True
    )
    dc1: Mapped[dict] = mapped_column(JSONB, default=dict)
    dc2: Mapped[dict] = mapped_column(JSONB, default=dict)
    dc4: Mapped[dict] = mapped_column(JSONB, default=dict)
    acte_engagement: Mapped[dict] = mapped_column(JSONB, default=dict)
    statut: Mapped[str] = mapped_column(String(20), default="brouillon")

    projet: Mapped[Projet] = relationship(back_populates="env_admin")


class EnveloppeTechnique(Base, TimestampMixin):
    __tablename__ = "enveloppe_technique"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    projet_id: Mapped[UUID] = mapped_column(
        ForeignKey("projets.id", ondelete="CASCADE"), unique=True, index=True
    )
    memoire_md: Mapped[str] = mapped_column(Text, default="")
    memoire_html: Mapped[str] = mapped_column(Text, default="")
    version: Mapped[int] = mapped_column(Integer, default=1)
    statut: Mapped[str] = mapped_column(String(20), default="brouillon")

    projet: Mapped[Projet] = relationship(back_populates="env_technique")


class EnveloppeFinanciere(Base, TimestampMixin):
    """L'enveloppe financière est physiquement isolée (collection vectorielle
    séparée + table dédiée) pour respecter la règle d'indépendance."""
    __tablename__ = "enveloppe_financiere"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    projet_id: Mapped[UUID] = mapped_column(
        ForeignKey("projets.id", ondelete="CASCADE"), unique=True, index=True
    )
    dpgf: Mapped[list] = mapped_column(JSONB, default=list)   # liste de lignes
    bpu: Mapped[list] = mapped_column(JSONB, default=list)
    total_ht: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    total_ttc: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    statut: Mapped[str] = mapped_column(String(20), default="brouillon")

    projet: Mapped[Projet] = relationship(back_populates="env_financiere")


# ---------- Audit ----------
class AuditLog(Base):
    """Journal d'audit : chaque action sensible est tracée (exigé en on-prem BTP)."""
    __tablename__ = "audit_log"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    horodatage: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    action: Mapped[str] = mapped_column(String(100), index=True)
    cible_type: Mapped[str | None] = mapped_column(String(50))
    cible_id: Mapped[UUID | None] = mapped_column()
    detail: Mapped[dict] = mapped_column(JSONB, default=dict)
