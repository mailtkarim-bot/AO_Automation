"""Configuration de l'application (chargée depuis l'environnement).

Toutes les valeurs sensibles viennent du fichier .env. En on-prem, le
client renseigne son propre .env au moment de l'installation.
"""
from functools import lru_cache
from uuid import UUID

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ----- App -----
    app_env: str = "dev"
    app_name: str = "batiao"
    secret_key: str = Field(default="dev-only-change-me", min_length=16)
    log_level: str = "INFO"

    # ----- Multi-tenant -----
    default_tenant_id: UUID = UUID("00000000-0000-0000-0000-000000000001")

    # ----- Base de données -----
    database_url: str = "postgresql+psycopg://batiao:batiao@db:5432/batiao"
    postgres_host: str = "db"
    postgres_port: int = 5432

    # ----- MinIO (stockage fichiers) -----
    minio_endpoint: str = "minio:9000"
    minio_bucket: str = "batiao-docs"
    minio_root_user: str = "batiao"
    minio_root_password: str = "batiao-super-secret"
    minio_use_ssl: bool = False

    # ----- Redis / Celery -----
    redis_url: str = "redis://redis:6379/0"

    # ----- LLM (Mistral souverain FR) -----
    llm_backend: str = "mistral_api"  # "mistral_api" | "local"
    mistral_api_key: str = ""
    mistral_model_large: str = "mistral-large-latest"
    mistral_model_medium: str = "mistral-medium-latest"
    mistral_model_small: str = "mistral-small-latest"
    mistral_embed_model: str = "mistral-embed"
    local_llm_base_url: str = "http://localhost:11434/v1"
    local_llm_model: str = "mistral-nemo"

    # ----- RAG -----
    embedding_dim: int = 1024  # dimension des embeddings Mistral (mistral-embed)
    chunk_size: int = 1200     # caractères cible par chunk
    chunk_overlap: int = 200
    retrieval_top_k: int = 8

    @property
    def is_dev(self) -> bool:
        return self.app_env == "dev"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
