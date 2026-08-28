import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.models.environment import Environment
from app.models.feature_flag import FeatureFlag
from app.models.project import Project
from app.models.rule_condition import RuleCondition
from app.models.targeting_rule import TargetingRule
from app.schemas.targeting_rule import TargetingRuleCreate, TargetingRuleResponse


router = APIRouter(tags=["Targeting Rules"])

DatabaseSession = Annotated[Session, Depends(get_db)]

RULES_PATH = (
    "/tenants/{tenant_id}/projects/{project_id}"
    "/environments/{environment_id}/flags/{flag_key}/rules"
)


def get_flag_for_ownership_chain(
    db: Session,
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    environment_id: uuid.UUID,
    flag_key: str,
) -> FeatureFlag:
    flag = db.scalar(
        select(FeatureFlag)
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

    return flag


@router.post(
    RULES_PATH,
    response_model=TargetingRuleResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_rule(
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    environment_id: uuid.UUID,
    flag_key: str,
    payload: TargetingRuleCreate,
    db: DatabaseSession,
) -> TargetingRule:
    flag = get_flag_for_ownership_chain(
        db, tenant_id, project_id, environment_id, flag_key
    )

    existing_rule = db.scalar(
        select(TargetingRule).where(
            TargetingRule.feature_flag_id == flag.id,
            TargetingRule.priority == payload.priority,
        )
    )

    if existing_rule is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A rule with this priority already exists",
        )

    rule = TargetingRule(
        feature_flag_id=flag.id,
        priority=payload.priority,
    )

    if payload.serve.type == "fixed":
        rule.serve_type = "fixed"
        rule.serve_value = payload.serve.value
        rule.true_basis_points = None
    else:
        rule.serve_type = "percentage"
        rule.serve_value = None
        rule.true_basis_points = payload.serve.true_basis_points

    rule.conditions = [
        RuleCondition(
            attribute=condition.attribute,
            operator=condition.operator,
            value=condition.value,
        )
        for condition in payload.conditions
    ]

    db.add(rule)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A rule with this priority already exists",
        ) from exc

    db.refresh(rule)
    return rule


@router.get(
    RULES_PATH,
    response_model=list[TargetingRuleResponse],
)
def list_rules(
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    environment_id: uuid.UUID,
    flag_key: str,
    db: DatabaseSession,
) -> list[TargetingRule]:
    flag = get_flag_for_ownership_chain(
        db, tenant_id, project_id, environment_id, flag_key
    )

    return list(
        db.scalars(
            select(TargetingRule)
            .options(selectinload(TargetingRule.conditions))
            .where(TargetingRule.feature_flag_id == flag.id)
            .order_by(TargetingRule.priority)
        ).all()
    )


@router.delete(
    f"{RULES_PATH}/{{rule_id}}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_rule(
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    environment_id: uuid.UUID,
    flag_key: str,
    rule_id: uuid.UUID,
    db: DatabaseSession,
) -> Response:
    flag = get_flag_for_ownership_chain(
        db, tenant_id, project_id, environment_id, flag_key
    )
    rule = db.scalar(
        select(TargetingRule).where(
            TargetingRule.id == rule_id,
            TargetingRule.feature_flag_id == flag.id,
        )
    )

    if rule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Targeting rule not found",
        )

    db.delete(rule)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
