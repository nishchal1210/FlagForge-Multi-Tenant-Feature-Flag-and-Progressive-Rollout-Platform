
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.tenant import Tenant
from app.schemas.tenant import TenantCreate, TenantResponse


router = APIRouter(prefix="/tenants", tags=["Tenants"])

DatabaseSession = Annotated[Session, Depends(get_db)]


@router.post(
    "",
    response_model=TenantResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_tenant(
    payload: TenantCreate,
    db: DatabaseSession,
) -> Tenant:
    existing = db.scalar(
        select(Tenant).where(Tenant.name == payload.name)
    )

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Tenant with this name already exists",
        )

    tenant = Tenant(name=payload.name)

    db.add(tenant)
    db.commit()
    db.refresh(tenant)

    return tenant


@router.get("", response_model=list[TenantResponse])
def list_tenants(db: DatabaseSession) -> list[Tenant]:
    return list(
        db.scalars(
            select(Tenant).order_by(Tenant.created_at)
        ).all()
    )


@router.get(
    "/{tenant_id}",
    response_model=TenantResponse,
)
def get_tenant(
    tenant_id: uuid.UUID,
    db: DatabaseSession,
) -> Tenant:
    tenant = db.get(Tenant, tenant_id)

    if tenant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )

    return tenant