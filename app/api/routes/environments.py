import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.environment import Environment
from app.models.project import Project
from app.schemas.environment import EnvironmentCreate, EnvironmentResponse


router = APIRouter(tags=["Environments"])

DatabaseSession = Annotated[Session, Depends(get_db)]


def get_project_for_tenant(
    db: Session,
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
) -> Project:
    project = db.scalar(
        select(Project).where(
            Project.id == project_id,
            Project.tenant_id == tenant_id,
        )
    )

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found for this tenant",
        )

    return project


@router.post(
    "/tenants/{tenant_id}/projects/{project_id}/environments",
    response_model=EnvironmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_environment(
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    payload: EnvironmentCreate,
    db: DatabaseSession,
) -> Environment:
    project = get_project_for_tenant(db, tenant_id, project_id)

    existing = db.scalar(
        select(Environment).where(
            Environment.project_id == project.id,
            Environment.key == payload.key,
        )
    )

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Environment key already exists for this project",
        )

    environment = Environment(
        project_id=project.id,
        name=payload.name,
        key=payload.key,
    )

    db.add(environment)
    db.commit()
    db.refresh(environment)

    return environment


@router.get(
    "/tenants/{tenant_id}/projects/{project_id}/environments",
    response_model=list[EnvironmentResponse],
)
def list_environments(
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    db: DatabaseSession,
) -> list[Environment]:
    project = get_project_for_tenant(db, tenant_id, project_id)

    return list(
        db.scalars(
            select(Environment).where(
                Environment.project_id == project.id
            )
        ).all()
    )
