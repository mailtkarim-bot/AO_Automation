"""Schémas Pydantic — validation des entrées/sorties de l'API."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ---------- Tenants ----------
class TenantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    nom: str
    siret: str | None = None


# ---------- Projets ----------
class ProjetCreate(BaseModel):
    intitule: str = Field(..., min_length=3, max_length=1000)
    maitre_ouvrage: str | None = None
    lieu: str | None = None
    montant_estime: Decimal | None = None
    procedure: str | None = Field(default=None, description="MAPA | FORMALISEE")
    ccag: str | None = None
    date_remise: date | None = None
    metadonnees: dict = Field(default_factory=dict)


class ProjetUpdate(BaseModel):
    intitule: str | None = None
    maitre_ouvrage: str | None = None
    lieu: str | None = None
    montant_estime: Decimal | None = None
    procedure: str | None = None
    ccag: str | None = None
    date_remise: date | None = None
    statut: str | None = None
    metadonnees: dict | None = None


class ProjetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    tenant_id: UUID
    intitule: str
    maitre_ouvrage: str | None
    lieu: str | None
    montant_estime: Decimal | None
    procedure: str | None
    ccag: str | None
    date_remise: date | None
    statut: str
    metadonnees: dict
    created_at: object
    nb_documents: int = 0
    nb_chunks: int = 0


# ---------- Documents ----------
class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    projet_id: UUID
    type: str
    nom_fichier: str
    taille_octets: int
    mime_type: str | None
    statut: str
    nb_pages: int | None
    erreur: str | None
    created_at: object


# ---------- Chat ----------
class ChatRequest(BaseModel):
    question: str = Field(..., min_length=2)
    enveloppe: str | None = Field(default=None, description="GEN | FINANCIERE")
    history: list[dict] = Field(default_factory=list)


class ChatSource(BaseModel):
    document: str
    type: str
    page: int | None
    section: str | None
    score: float


class ChatResponse(BaseModel):
    reponse: str
    sources: list[ChatSource]
    usage: dict | None = None
