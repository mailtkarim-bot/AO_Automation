"""Routes /projets — création, liste, détail."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_tenant
from app.core.db import get_db
from app.db import Document, DocumentChunk, Projet
from app.schemas import ProjetCreate, ProjetOut, ProjetUpdate

router = APIRouter(prefix="/projets", tags=["projets"])


@router.post("", response_model=ProjetOut, status_code=status.HTTP_201_CREATED)
def create_projet(payload: ProjetCreate, db: Session = Depends(get_db),
                  tenant=Depends(get_current_tenant)) -> ProjetOut:
    p = Projet(tenant_id=tenant.id, **payload.model_dump())
    db.add(p)
    db.commit()
    db.refresh(p)
    return _to_out(db, p)


@router.get("", response_model=list[ProjetOut])
def list_projets(db: Session = Depends(get_db),
                 tenant=Depends(get_current_tenant)) -> list[ProjetOut]:
    rows = db.scalars(
        select(Projet).where(Projet.tenant_id == tenant.id).order_by(Projet.created_at.desc())
    ).all()
    return [_to_out(db, p) for p in rows]


@router.get("/{projet_id}", response_model=ProjetOut)
def get_projet(projet_id: UUID, db: Session = Depends(get_db),
               tenant=Depends(get_current_tenant)) -> ProjetOut:
    p = db.get(Projet, projet_id)
    if not p or p.tenant_id != tenant.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Projet introuvable.")
    return _to_out(db, p)


@router.patch("/{projet_id}", response_model=ProjetOut)
def update_projet(projet_id: UUID, payload: ProjetUpdate, db: Session = Depends(get_db),
                  tenant=Depends(get_current_tenant)) -> ProjetOut:
    p = db.get(Projet, projet_id)
    if not p or p.tenant_id != tenant.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Projet introuvable.")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(p, k, v)
    db.commit()
    db.refresh(p)
    return _to_out(db, p)


@router.delete("/{projet_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_projet(projet_id: UUID, db: Session = Depends(get_db),
                  tenant=Depends(get_current_tenant)) -> None:
    p = db.get(Projet, projet_id)
    if not p or p.tenant_id != tenant.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Projet introuvable.")
    db.delete(p)
    db.commit()


def _to_out(db: Session, p: Projet) -> ProjetOut:
    nb_docs = db.scalar(select(func.count(Document.id)).where(Document.projet_id == p.id)) or 0
    nb_chunks = db.scalar(
        select(func.count(DocumentChunk.id)).where(DocumentChunk.projet_id == p.id)
    ) or 0
    return ProjetOut(
        id=p.id, tenant_id=p.tenant_id, intitule=p.intitule, maitre_ouvrage=p.maitre_ouvrage,
        lieu=p.lieu, montant_estime=p.montant_estime, procedure=p.procedure, ccag=p.ccag,
        date_remise=p.date_remise, statut=p.statut, metadonnees=p.metadonnees,
        created_at=p.created_at, nb_documents=nb_docs, nb_chunks=nb_chunks,
    )
