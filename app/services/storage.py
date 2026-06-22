"""Stockage fichiers — abstraction S3 (MinIO en on-prem).

Le contenu des documents reste local (RGPD). On expose put/get/delete.
"""
from __future__ import annotations

import io
from uuid import UUID

import boto3
from botocore.client import Config as BotoConfig

from app.core.config import settings


def _client():
    return boto3.client(
        "s3",
        endpoint_url=f"{'https' if settings.minio_use_ssl else 'http'}://{settings.minio_endpoint}",
        aws_access_key_id=settings.minio_root_user,
        aws_secret_access_key=settings.minio_root_password,
        config=BotoConfig(signature_version="s3v4"),
        region_name="us-east-1",
    )


def _bucket() -> str:
    return settings.minio_bucket


def ensure_bucket() -> None:
    s3 = _client()
    try:
        s3.head_bucket(Bucket=_bucket())
    except Exception:
        s3.create_bucket(Bucket=_bucket())


def object_key(projet_id: UUID, doc_id: UUID, nom_fichier: str) -> str:
    """Hiérarchie : /<tenant_via_projet>/<projet>/<doc>/<fichier>.
    Le projet porte déjà le tenant (FK). On simplifie en projet/doc."""
    return f"projets/{projet_id}/{doc_id}/{nom_fichier}"


def upload_bytes(projet_id: UUID, doc_id: UUID, nom_fichier: str, data: bytes,
                 content_type: str = "application/octet-stream") -> str:
    ensure_bucket()
    key = object_key(projet_id, doc_id, nom_fichier)
    _client().put_object(Bucket=_bucket(), Key=key, Body=data, ContentType=content_type)
    return key


def download_bytes(chemin: str) -> bytes:
    obj = _client().get_object(Bucket=_bucket(), Key=chemin)
    return obj["Body"].read()


def delete_object(chemin: str) -> None:
    _client().delete_object(Bucket=_bucket(), Key=chemin)
