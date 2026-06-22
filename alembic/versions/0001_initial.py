"""Schéma initial Batião : tenants, projets, documents, chunks, enveloppes.

Revision ID: 0001
Revises:
Create Date: 2026-06-21
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Extension vectorielle (nécessaire pour le type pgvector)
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")     # recherche floue
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent")    # accents FR

    # ---------- Tenants & users ----------
    op.create_table(
        "tenants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("nom", sa.String(255), nullable=False),
        sa.Column("siret", sa.String(20)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("email", sa.String(320), nullable=False, index=True),
        sa.Column("nom_complet", sa.String(255)),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("role", sa.String(50), nullable=False, server_default="user"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ---------- Bibliothèque d'entreprise ----------
    op.create_table(
        "biblio_memoires",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("titre", sa.String(500), nullable=False),
        sa.Column("corps", sa.Text, nullable=False),
        sa.Column("metadonnees", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "biblio_bpu",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("ouvrage", sa.String(500), nullable=False),
        sa.Column("unite", sa.String(20), nullable=False),
        sa.Column("prix_ht", sa.Numeric(12, 2), nullable=False),
        sa.Column("date_validite", sa.Date),
        sa.Column("metadonnees", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "biblio_attestations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("type", sa.String(50), nullable=False, index=True),
        sa.Column("nom_fichier", sa.String(500), nullable=False),
        sa.Column("chemin_stockage", sa.String(1000), nullable=False),
        sa.Column("expire_le", sa.Date, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ---------- Projet ----------
    op.create_table(
        "projets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("intitule", sa.String(1000), nullable=False),
        sa.Column("maitre_ouvrage", sa.String(500)),
        sa.Column("lieu", sa.String(500)),
        sa.Column("montant_estime", sa.Numeric(14, 2)),
        sa.Column("procedure", sa.String(50)),
        sa.Column("ccag", sa.String(100)),
        sa.Column("date_remise", sa.Date, index=True),
        sa.Column("statut", sa.String(50), nullable=False, server_default="cree", index=True),
        sa.Column("metadonnees", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ---------- Documents ----------
    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("projet_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("projets.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("type", sa.String(20), nullable=False, index=True),
        sa.Column("nom_fichier", sa.String(500), nullable=False),
        sa.Column("chemin_stockage", sa.String(1000), nullable=False),
        sa.Column("hash", sa.String(64), nullable=False, index=True),
        sa.Column("taille_octets", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("mime_type", sa.String(100)),
        sa.Column("statut", sa.String(20), nullable=False, server_default="EN_ATTENTE", index=True),
        sa.Column("nb_pages", sa.Integer),
        sa.Column("texte_complet", sa.Text),
        sa.Column("erreur", sa.Text),
        sa.Column("parsed_at", sa.DateTime(timezone=True)),
        sa.Column("vectorized_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # Index full-text (CCTP, CCAP...) avec support des accents français
    op.execute(
        "CREATE INDEX documents_texte_fts ON documents "
        "USING GIN (to_tsvector('french', unaccent(coalesce(texte_complet,''))))"
    )

    # ---------- Chunks (RAG) ----------
    op.create_table(
        "document_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("projet_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("projets.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("enveloppe", sa.String(20), nullable=False, server_default="GEN", index=True),
        sa.Column("ordinal", sa.Integer, nullable=False),
        sa.Column("texte", sa.Text, nullable=False),
        sa.Column("page_source", sa.Integer),
        sa.Column("section", sa.String(500)),
        sa.Column("embedding", Vector(1024)),
    )
    # HNSW = index vectoriel rapide (recherche de similarité)
    op.execute(
        "CREATE INDEX document_chunks_embedding_idx ON document_chunks "
        "USING hnsw (embedding vector_cosine_ops)"
    )
    # Index composite projet + enveloppe = filtre d'isolation à la volée
    op.create_index(
        "document_chunks_projet_enveloppe_idx",
        "document_chunks",
        ["projet_id", "enveloppe"],
    )

    # ---------- Extractions IA ----------
    op.create_table(
        "analyses_go_nogo",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("projet_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("projets.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("verdict", sa.String(20), nullable=False, index=True),
        sa.Column("score", sa.Integer, nullable=False),
        sa.Column("synthese", sa.Text, nullable=False),
        sa.Column("red_flags", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'")),
        sa.Column("points_forts", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'")),
        sa.Column("detail", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'")),
        sa.Column("model_used", sa.String(100)),
        sa.Column("prompt_version", sa.String(50)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "criteres_selection",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("projet_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("projets.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("critere", sa.String(500), nullable=False),
        sa.Column("ponderation", sa.Numeric(5, 2)),
        sa.Column("sous_criteres", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'")),
        sa.Column("source_doc_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "ouvrages_cctp",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("projet_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("projets.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("lot", sa.String(200), index=True),
        sa.Column("designation", sa.Text, nullable=False),
        sa.Column("unite", sa.String(20)),
        sa.Column("quantite", sa.Numeric(14, 3)),
        sa.Column("description", sa.Text),
        sa.Column("source_doc_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "clauses_sensibles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("projet_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("projets.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("type", sa.String(50), nullable=False, index=True),
        sa.Column("libelle", sa.Text, nullable=False),
        sa.Column("severite", sa.String(20), nullable=False, server_default="INFO"),
        sa.Column("source_doc_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id")),
        sa.Column("page_source", sa.Integer),
        sa.Column("detail", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "echeances",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("projet_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("projets.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("date", sa.Date, nullable=False, index=True),
        sa.Column("commentaire", sa.Text),
        sa.Column("source_doc_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ---------- 3 enveloppes ----------
    op.create_table(
        "enveloppe_administrative",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("projet_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("projets.id", ondelete="CASCADE"), nullable=False, unique=True, index=True),
        sa.Column("dc1", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'")),
        sa.Column("dc2", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'")),
        sa.Column("dc4", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'")),
        sa.Column("acte_engagement", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'")),
        sa.Column("statut", sa.String(20), nullable=False, server_default="brouillon"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "enveloppe_technique",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("projet_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("projets.id", ondelete="CASCADE"), nullable=False, unique=True, index=True),
        sa.Column("memoire_md", sa.Text, nullable=False, server_default=""),
        sa.Column("memoire_html", sa.Text, nullable=False, server_default=""),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("statut", sa.String(20), nullable=False, server_default="brouillon"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "enveloppe_financiere",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("projet_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("projets.id", ondelete="CASCADE"), nullable=False, unique=True, index=True),
        sa.Column("dpgf", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'")),
        sa.Column("bpu", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'")),
        sa.Column("total_ht", sa.Numeric(14, 2)),
        sa.Column("total_ttc", sa.Numeric(14, 2)),
        sa.Column("statut", sa.String(20), nullable=False, server_default="brouillon"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ---------- Audit ----------
    op.create_table(
        "audit_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("horodatage", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False, index=True),
        sa.Column("action", sa.String(100), nullable=False, index=True),
        sa.Column("cible_type", sa.String(50)),
        sa.Column("cible_id", postgresql.UUID(as_uuid=True)),
        sa.Column("detail", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'")),
    )


def downgrade() -> None:
    for table in (
        "audit_log",
        "enveloppe_financiere",
        "enveloppe_technique",
        "enveloppe_administrative",
        "echeances",
        "clauses_sensibles",
        "ouvrages_cctp",
        "criteres_selection",
        "analyses_go_nogo",
        "document_chunks",
        "documents",
        "projets",
        "biblio_attestations",
        "biblio_bpu",
        "biblio_memoires",
        "users",
        "tenants",
    ):
        op.drop_table(table)
