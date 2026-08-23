import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.project import Project
from app.models.tenant import Tenant
from app.schemas.project import ProjectCreate, ProjectResponse


router = APIRouter(tags=["Projects"])

DatabaseSession = Annotated[Session, Depends(get_db)]


@router.post(
    "/tenants/{tenant_id}/projects",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_project(
    tenant_id: uuid.UUID,
    payload: ProjectCreate,
    db: DatabaseSession,
) -> Project:
    tenant = db.get(Tenant, tenant_id)

    if tenant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )

    existing = db.scalar(
        select(Project).where(
            Project.tenant_id == tenant_id,
            Project.key == payload.key,
        )
    )

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Project key already exists for this tenant",
        )

    project = Project(
        tenant_id=tenant_id,
        name=payload.name,
        key=payload.key,
    )

    db.add(project)
    db.commit()
    db.refresh(project)

    return project


@router.get(
    "/tenants/{tenant_id}/projects",
    response_model=list[ProjectResponse],
)
def list_projects(
    tenant_id: uuid.UUID,
    db: DatabaseSession,
) -> list[Project]:
    return list(
        db.scalars(
            select(Project).where(
                Project.tenant_id == tenant_id
            )
        ).all()
    )
