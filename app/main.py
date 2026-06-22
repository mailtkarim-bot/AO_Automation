"""Point d'entrée FastAPI — Batião backend."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app import __version__
from app.api import chat, documents, projets, tri
from app.core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Démarrage de {settings.app_name} v{__version__} (env={settings.app_env})")
    logger.info(f"Backend LLM : {settings.llm_backend}")
    yield
    logger.info("Arrêt propre.")


app = FastAPI(
    title="Batião API",
    description="Copilote IA de réponse aux appels d'offres BTP.",
    version=__version__,
    lifespan=lifespan,
)

# CORS — large en dev, à restreindre en prod on-prem
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.is_dev else ["http://localhost:8501"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projets.router, prefix="/api/v1")
app.include_router(documents.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")
app.include_router(tri.router, prefix="/api/v1")


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok", "app": settings.app_name, "version": __version__}


@app.get("/", tags=["meta"])
def root() -> dict:
    return {
        "service": settings.app_name,
        "version": __version__,
        "docs": "/docs",
    }
