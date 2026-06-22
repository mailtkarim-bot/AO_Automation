"""Routes /projets/{id}/documents — upload + ingestion + retraitement."""
import hashlib
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_tenant
from app.core.db import get_db
from app.db import Document, Projet
from app.schemas import DocumentOut
from app.services import storage
from app.services.classifier import classify
from app.services.parser import parse_bytes, unzip_dce
from app.services.rag import index_document

router = APIRouter(prefix="/projets/{projet_id}/documents", tags=["documents"])


@router.post("", response_model=list[DocumentOut], status_code=status.HTTP_201_CREATED)
async def upload_documents(
    projet_id: UUID,
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    tenant=Depends(get_current_tenant),
) -> list[DocumentOut]:
    p = db.get(Projet, projet_id)
    if not p or p.tenant_id != tenant.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Projet introuvable.")

    results: list[DocumentOut] = []
    for upload in files:
        raw = await upload.read()
        # Un ZIP de DCE → on l'éclate en plusieurs pièces
        if upload.filename.lower().endswith(".zip"):
            for nom, data in unzip_dce(raw):
                results.append(_ingest(db, p.id, nom, data, _mime(nom)))
            continue
        results.append(_ingest(db, p.id, upload.filename, raw, upload.content_type))
    return results


def _ingest(db: Session, projet_id: UUID, nom: str, data: bytes, mime: str | None) -> DocumentOut:
    h = hashlib.sha256(data).hexdigest()
    doc = Document(
        projet_id=projet_id,
        type="AUTRE",  # sera affiné par le classifieur
        nom_fichier=nom,
        chemin_stockage="pending",
        hash=h,
        taille_octets=len(data),
        mime_type=mime,
        statut="EN_COURS",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    try:
        # 1. Stockage
        chemin = storage.upload_bytes(projet_id, doc.id, nom, data, mime or "application/octet-stream")
        doc.chemin_stockage = chemin

        # 2. Parsing
        parsed = parse_bytes(data, nom, mime)
        doc.texte_complet = parsed.texte_brut[:500_000]  # on garde une limite raisonnable
        doc.nb_pages = parsed.nb_pages

        # 3. Classification
        cls = classify(parsed)
        doc.type = cls.type

        # 4. Vectorisation (RAG)
        doc.statut = "PARSE_OK"
        doc.parsed_at = datetime.utcnow()
        db.commit()
        nb = index_document(db, doc, parsed)

        return DocumentOut(
            id=doc.id, projet_id=doc.projet_id, type=doc.type, nom_fichier=doc.nom_fichier,
            taille_octets=doc.taille_octets, mime_type=doc.mime_type, statut=doc.statut,
            nb_pages=doc.nb_pages, erreur=None, created_at=doc.created_at,
        )
    except Exception as e:
        doc.statut = "ERREUR"
        doc.erreur = str(e)
        db.commit()
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Échec de l'ingestion de {nom} : {e}",
        )


@router.get("", response_model=list[DocumentOut])
def list_documents(projet_id: UUID, db: Session = Depends(get_db),
                   tenant=Depends(get_current_tenant)) -> list[DocumentOut]:
    p = db.get(Projet, projet_id)
    if not p or p.tenant_id != tenant.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Projet introuvable.")
    docs = sorted(p.documents, key=lambda d: d.created_at)
    return [DocumentOut.model_validate(d) for d in docs]


def _mime(nom: str) -> str | None:
    n = nom.lower()
    if n.endswith(".pdf"):
        return "application/pdf"
    if n.endswith(".docx"):
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    if n.endswith(".xlsx"):
        return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return None
