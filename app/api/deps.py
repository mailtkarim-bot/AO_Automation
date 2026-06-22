"""Dépendances communes : tenant courant, projet."""
from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.db import Projet, Tenant


def get_current_tenant(db: Session = Depends(get_db)) -> Tenant:
    """En M0/M1, on fonctionne en mono-tenant via DEFAULT_TENANT_ID.
    L'authentification complète (JWT, RBAC) arrive en M4."""
    tenant = db.get(Tenant, settings.default_tenant_id)
    if not tenant:
        # Auto-création du tenant par défaut pour le dev
        tenant = Tenant(id=settings.default_tenant_id, nom="Tenant par défaut")
        db.add(tenant)
        db.commit()
        db.refresh(tenant)
    return tenant


def get_projet(projet_id: UUID, db: Session = Depends(get_db),
               tenant: Tenant = Depends(get_current_tenant)) -> Projet:
    p = db.get(Projet, projet_id)
    if not p or p.tenant_id != tenant.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Projet introuvable.")
    return p
