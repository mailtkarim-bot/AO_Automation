"""Agrégation des routeurs API."""
from fastapi import APIRouter

from app.api import chat, documents, projets

api_router = APIRouter()
api_router.include_router(projets.router)
api_router.include_router(documents.router)
api_router.include_router(chat.router)
