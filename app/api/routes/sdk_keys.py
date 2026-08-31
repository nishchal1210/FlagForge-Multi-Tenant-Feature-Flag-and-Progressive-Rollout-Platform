import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.environment import Environment
from app.models.environment_sdk_key import EnvironmentSDKKey
from app.models.project import Project
from app.schemas.sdk_key import SDKKeyCreate, SDKKeyCreatedResponse, SDKKeyResponse
from app.security.sdk_keys import generate_sdk_key


router = APIRouter(tags=["SDK Keys"])

DatabaseSession = Annotated[Session, Depends(get_db)]


def get_environment(
    db: Session,
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    environment_id: uuid.UUID,
) -> Environment:
    environment = db.scalar(
        select(Environment)
        .join(Project)
        .where(
            Environment.id == environment_id,
            Environment.project_id == project_id,
            Project.id == project_id,
            Project.tenant_id == tenant_id,
        )
    )

    if environment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Environment not found",
        )

    return environment


@router.post(
    "/tenants/{tenant_id}/projects/{project_id}/environments/"
    "{environment_id}/sdk-keys",
    response_model=SDKKeyCreatedResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_sdk_key(
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    environment_id: uuid.UUID,
    payload: SDKKeyCreate,
    db: DatabaseSession,
) -> SDKKeyCreatedResponse:
    environment = get_environment(db, tenant_id, project_id, environment_id)

    existing = db.scalar(
        select(EnvironmentSDKKey).where(
            EnvironmentSDKKey.environment_id == environment.id,
            EnvironmentSDKKey.name == payload.name,
        )
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="SDK key name already exists",
        )

    key_id = uuid.uuid4()
    plain_key, key_hash = generate_sdk_key(key_id)
    sdk_key = EnvironmentSDKKey(
        id=key_id,
        environment_id=environment.id,
        name=payload.name,
        key_hash=key_hash,
    )

    db.add(sdk_key)
    db.commit()
    db.refresh(sdk_key)

    return SDKKeyCreatedResponse(
        id=sdk_key.id,
        environment_id=sdk_key.environment_id,
        name=sdk_key.name,
        key=plain_key,
        created_at=sdk_key.created_at,
    )


@router.get(
    "/tenants/{tenant_id}/projects/{project_id}/environments/"
    "{environment_id}/sdk-keys",
    response_model=list[SDKKeyResponse],
)
def list_sdk_keys(
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    environment_id: uuid.UUID,
    db: DatabaseSession,
) -> list[EnvironmentSDKKey]:
    environment = get_environment(db, tenant_id, project_id, environment_id)

    return list(
        db.scalars(
            select(EnvironmentSDKKey)
            .where(EnvironmentSDKKey.environment_id == environment.id)
            .order_by(EnvironmentSDKKey.created_at, EnvironmentSDKKey.id)
        ).all()
    )


@router.delete(
    "/tenants/{tenant_id}/projects/{project_id}/environments/"
    "{environment_id}/sdk-keys/{key_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def revoke_sdk_key(
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    environment_id: uuid.UUID,
    key_id: uuid.UUID,
    db: DatabaseSession,
) -> Response:
    environment = get_environment(db, tenant_id, project_id, environment_id)
    sdk_key = db.scalar(
        select(EnvironmentSDKKey).where(
            EnvironmentSDKKey.id == key_id,
            EnvironmentSDKKey.environment_id == environment.id,
        )
    )

    if sdk_key is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SDK key not found",
        )

    if sdk_key.revoked_at is None:
        sdk_key.revoked_at = datetime.now(timezone.utc)
        db.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)
