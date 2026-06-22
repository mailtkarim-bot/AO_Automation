"""Routes /chat — discuter avec le marché (RAG)."""
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_tenant
from app.core.db import get_db
from app.db import Projet
from app.schemas import ChatRequest, ChatResponse
from app.services.rag import answer_with_sources

router = APIRouter(prefix="/projets/{projet_id}/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
def chat(projet_id: UUID, payload: ChatRequest, db: Session = Depends(get_db),
         tenant=Depends(get_current_tenant)) -> ChatResponse:
    p = db.get(Projet, projet_id)
    if not p or p.tenant_id != tenant.id:
        from fastapi import HTTPException, status
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Projet introuvable.")
    res = answer_with_sources(db, p.id, payload.question,
                              enveloppe=payload.enveloppe, history=payload.history)
    return ChatResponse(**res)
