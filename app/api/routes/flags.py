import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.models.environment import Environment
from app.models.feature_flag import FeatureFlag
from app.models.project import Project
from app.models.targeting_rule import TargetingRule
from app.schemas.evaluation import EvaluationRequest, EvaluationResponse
from app.schemas.feature_flag import (
    FeatureFlagCreate,
    FeatureFlagResponse,
    FeatureFlagUpdate,
)
from app.services.evaluator import evaluate_flag


router = APIRouter(tags=["Feature Flags"])

DatabaseSession = Annotated[Session, Depends(get_db)]

FLAGS_PATH = (
    "/tenants/{tenant_id}/projects/{project_id}"
    "/environments/{environment_id}/flags"
)


def get_environment_for_tenant_and_project(
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
            detail="Environment not found for this tenant and project",
        )

    return environment


def get_flag_for_environment(
    db: Session,
    environment_id: uuid.UUID,
    flag_key: str,
) -> FeatureFlag:
    flag = db.scalar(
        select(FeatureFlag).where(
            FeatureFlag.environment_id == environment_id,
            FeatureFlag.key == flag_key,
        )
    )

    if flag is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Feature flag not found",
        )

    return flag


@router.post(
    FLAGS_PATH,
    response_model=FeatureFlagResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_flag(
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    environment_id: uuid.UUID,
    payload: FeatureFlagCreate,
    db: DatabaseSession,
) -> FeatureFlag:
    environment = get_environment_for_tenant_and_project(
        db, tenant_id, project_id, environment_id
    )

    existing = db.scalar(
        select(FeatureFlag).where(
            FeatureFlag.environment_id == environment.id,
            FeatureFlag.key == payload.key,
        )
    )

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Feature flag key already exists for this environment",
        )

    flag = FeatureFlag(
        environment_id=environment.id,
        key=payload.key,
        name=payload.name,
        enabled=payload.enabled,
        default_value=payload.default_value,
    )

    db.add(flag)
    db.commit()
    db.refresh(flag)

    return flag


@router.get(FLAGS_PATH, response_model=list[FeatureFlagResponse])
def list_flags(
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    environment_id: uuid.UUID,
    db: DatabaseSession,
) -> list[FeatureFlag]:
    environment = get_environment_for_tenant_and_project(
        db, tenant_id, project_id, environment_id
    )

    return list(
        db.scalars(
            select(FeatureFlag).where(
                FeatureFlag.environment_id == environment.id
            )
        ).all()
    )


@router.get(
    f"{FLAGS_PATH}/{{flag_key}}",
    response_model=FeatureFlagResponse,
)
def get_flag(
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    environment_id: uuid.UUID,
    flag_key: str,
    db: DatabaseSession,
) -> FeatureFlag:
    environment = get_environment_for_tenant_and_project(
        db, tenant_id, project_id, environment_id
    )
    return get_flag_for_environment(db, environment.id, flag_key)


@router.post(
    f"{FLAGS_PATH}/{{flag_key}}/evaluate",
    response_model=EvaluationResponse,
)
def evaluate_flag_preview(
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    environment_id: uuid.UUID,
    flag_key: str,
    payload: EvaluationRequest,
    db: DatabaseSession,
) -> EvaluationResponse:
    flag = db.scalar(
        select(FeatureFlag)
        .options(
            selectinload(FeatureFlag.rules)
            .selectinload(TargetingRule.conditions)
        )
        .join(FeatureFlag.environment)
        .join(Environment.project)
        .where(
            FeatureFlag.key == flag_key,
            FeatureFlag.environment_id == environment_id,
            Environment.id == environment_id,
            Environment.project_id == project_id,
            Project.id == project_id,
            Project.tenant_id == tenant_id,
        )
    )

    if flag is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Feature flag not found",
        )

    result = evaluate_flag(
        flag=flag,
        user=payload.user,
    )

    return EvaluationResponse(
        flag_key=flag.key,
        value=result.value,
        reason=result.reason,
        matched_rule_priority=result.matched_rule_priority,
        bucket=result.bucket,
    )


@router.patch(
    f"{FLAGS_PATH}/{{flag_key}}",
    response_model=FeatureFlagResponse,
)
def update_flag(
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    environment_id: uuid.UUID,
    flag_key: str,
    payload: FeatureFlagUpdate,
    db: DatabaseSession,
) -> FeatureFlag:
    environment = get_environment_for_tenant_and_project(
        db, tenant_id, project_id, environment_id
    )
    flag = get_flag_for_environment(db, environment.id, flag_key)

    updates = payload.model_dump(exclude_unset=True)

    for field, value in updates.items():
        setattr(flag, field, value)

    db.commit()
    db.refresh(flag)

    return flag


@router.delete(
    f"{FLAGS_PATH}/{{flag_key}}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_flag(
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    environment_id: uuid.UUID,
    flag_key: str,
    db: DatabaseSession,
) -> Response:
    environment = get_environment_for_tenant_and_project(
        db, tenant_id, project_id, environment_id
    )
    flag = get_flag_for_environment(db, environment.id, flag_key)

    db.delete(flag)
    db.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)
