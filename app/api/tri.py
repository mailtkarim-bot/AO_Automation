"""Route /projets/{id}/tri — lance l'agent Go/No-Go sur un projet."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.tri_go_nogo import analyser_marche
from app.api.deps import get_current_tenant
from app.core.db import get_db
from app.db import AnalyseGoNoGo, Document, Projet

router = APIRouter(prefix="/projets/{projet_id}/tri", tags=["tri"])


@router.post("")
def lancer_tri(projet_id: UUID, db: Session = Depends(get_db),
               tenant=Depends(get_current_tenant)) -> dict:
    p = db.get(Projet, projet_id)
    if not p or p.tenant_id != tenant.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Projet introuvable.")

    # On assemble le texte de TOUS les documents parsés (hors enveloppe prix)
    docs = db.scalars(
        select(Document).where(
            Document.projet_id == p.id,
            Document.texte_complet.isnot(None),
            Document.type.notin_(["BPU", "DPGF"]),
        )
    ).all()

    if not docs:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Aucun document indexé. Uploadez d'abord le DCE (CCTP, CCAP, RC...).",
        )

    texte_assemble = "\n\n".join(
        f"=== {d.nom_fichier} (type={d.type}) ===\n{d.texte_complet}"
        for d in docs
    )

    try:
        result = analyser_marche(texte_assemble)
    except Exception as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Échec de l'IA : {e}")

    # Persistance
    analyse = AnalyseGoNoGo(
        projet_id=p.id,
        verdict=result.verdict,
        score=result.score,
        synthese=result.synthese,
        red_flags=result.red_flags,
        points_forts=result.points_forts,
        detail=result.infos,
        model_used=result.model_used,
        prompt_version="tri-v1.0",
    )
    db.add(analyse)

    # On remonte aussi les infos clés sur le projet lui-même
    if result.infos.get("maitre_ouvrage") and not p.maitre_ouvrage:
        p.maitre_ouvrage = str(result.infos["maitre_ouvrage"])[:500]
    if result.infos.get("lieu") and not p.lieu:
        p.lieu = str(result.infos["lieu"])[:500]
    if result.infos.get("procedure") and not p.procedure:
        p.procedure = str(result.infos["procedure"])[:50]
    if result.infos.get("ccag") and not p.ccag:
        p.ccag = str(result.infos["ccag"])[:100]
    p.statut = "go" if result.verdict == "JOUER" else (
        "no_go" if result.verdict == "EVITER" else "en_analyse"
    )

    db.commit()
    db.refresh(analyse)

    return {
        "id": str(analyse.id),
        **result.to_dict(),
        "created_at": analyse.created_at.isoformat(),
    }


@router.get("")
def dernier_tri(projet_id: UUID, db: Session = Depends(get_db),
                tenant=Depends(get_current_tenant)) -> dict:
    p = db.get(Projet, projet_id)
    if not p or p.tenant_id != tenant.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Projet introuvable.")
    dernier = db.scalars(
        select(AnalyseGoNoGo).where(AnalyseGoNoGo.projet_id == p.id)
        .order_by(AnalyseGoNoGo.created_at.desc()).limit(1)
    ).first()
    if not dernier:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Aucune analyse Tri pour ce projet.")
    return {
        "id": str(dernier.id),
        "verdict": dernier.verdict,
        "score": dernier.score,
        "synthese": dernier.synthese,
        "red_flags": dernier.red_flags,
        "points_forts": dernier.points_forts,
        "detail": dernier.detail,
        "model_used": dernier.model_used,
        "prompt_version": dernier.prompt_version,
        "created_at": dernier.created_at.isoformat(),
    }
