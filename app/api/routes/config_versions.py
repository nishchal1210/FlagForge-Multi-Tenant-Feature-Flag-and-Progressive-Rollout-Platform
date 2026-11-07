import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.models.environment import Environment
from app.models.environment_config_version import (
    EnvironmentConfigVersion,
)
from app.models.feature_flag import FeatureFlag
from app.models.project import Project
from app.models.targeting_rule import TargetingRule
from app.schemas.config_version import ConfigVersionResponse
from app.schemas.config_version import ConfigVersionMetadata
from app.services.config_snapshot import (
    build_configuration,
    calculate_checksum,
)
import logging

from redis.exceptions import RedisError

from app.services.config_events import (
    publish_config_update,
)


logger = logging.getLogger(__name__)

router = APIRouter(tags=["Configuration Versions"])

DatabaseSession = Annotated[Session, Depends(get_db)]


@router.post(
    (
        "/tenants/{tenant_id}"
        "/projects/{project_id}"
        "/environments/{environment_id}"
        "/config/publish"
    ),
    response_model=ConfigVersionResponse,
    status_code=status.HTTP_201_CREATED,
)
def publish_configuration(
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    environment_id: uuid.UUID,
    db: DatabaseSession,
) -> EnvironmentConfigVersion:
    environment = db.scalar(
        select(Environment)
        .options(
            selectinload(Environment.flags)
            .selectinload(FeatureFlag.rules)
            .selectinload(TargetingRule.conditions)
        )
        .join(Environment.project)
        .where(
            Environment.id == environment_id,
            Environment.project_id == project_id,
            Project.id == project_id,
            Project.tenant_id == tenant_id,
        )
        .with_for_update()
    )

    if environment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Environment not found",
        )

    configuration = build_configuration(environment)
    checksum = calculate_checksum(configuration)

    if environment.published_version > 0:
        latest = db.scalar(
            select(EnvironmentConfigVersion).where(
                EnvironmentConfigVersion.environment_id
                == environment.id,
                EnvironmentConfigVersion.version
                == environment.published_version,
            )
        )

        if latest and latest.checksum == checksum:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Configuration has not changed "
                    "since the latest publication"
                ),
            )

    next_version = environment.published_version + 1

    config_version = EnvironmentConfigVersion(
        environment_id=environment.id,
        version=next_version,
        configuration=configuration,
        checksum=checksum,
    )

    environment.published_version = next_version

    db.add(config_version)
    db.commit()
    db.refresh(config_version)

    try:
        publish_config_update(
            environment_id=environment.id,
            version=config_version.version,
            checksum=config_version.checksum,
        )
    except RedisError:
        logger.exception(
            "Failed to publish configuration update event"
        )

    return config_version


@router.get(
    (
        "/tenants/{tenant_id}"
        "/projects/{project_id}"
        "/environments/{environment_id}"
        "/config/latest"
    ),
    response_model=ConfigVersionResponse,
)
def get_latest_configuration(
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    environment_id: uuid.UUID,
    db: DatabaseSession,
) -> EnvironmentConfigVersion:
    config_version = db.scalar(
        select(EnvironmentConfigVersion)
        .join(Environment)
        .join(Project)
        .where(
            EnvironmentConfigVersion.environment_id
            == environment_id,
            Environment.project_id == project_id,
            Project.id == project_id,
            Project.tenant_id == tenant_id,
            EnvironmentConfigVersion.version
            == Environment.published_version,
        )
    )

    if config_version is None:
        raise HTTPException(
            status_code=404,
            detail="No published configuration found",
        )

    return config_version



@router.get(
    (
        "/tenants/{tenant_id}"
        "/projects/{project_id}"
        "/environments/{environment_id}"
        "/config/versions/{version}"
    ),
    response_model=ConfigVersionResponse,
)
def get_configuration_version(
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    environment_id: uuid.UUID,
    version: int,
    db: DatabaseSession,
) -> EnvironmentConfigVersion:
    config_version = db.scalar(
        select(EnvironmentConfigVersion)
        .join(Environment)
        .join(Project)
        .where(
            EnvironmentConfigVersion.environment_id
            == environment_id,
            EnvironmentConfigVersion.version == version,
            Environment.project_id == project_id,
            Project.id == project_id,
            Project.tenant_id == tenant_id,
        )
    )

    if config_version is None:
        raise HTTPException(
            status_code=404,
            detail="Configuration version not found",
        )

    return config_version

@router.get(
    (
        "/tenants/{tenant_id}"
        "/projects/{project_id}"
        "/environments/{environment_id}"
        "/config/versions"
    ),
    response_model=list[ConfigVersionMetadata],
)
def list_configuration_versions(
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    environment_id: uuid.UUID,
    db: DatabaseSession,
) -> list[EnvironmentConfigVersion]:
    versions = db.scalars(
        select(EnvironmentConfigVersion)
        .join(Environment)
        .join(Project)
        .where(
            EnvironmentConfigVersion.environment_id
            == environment_id,
            Environment.project_id == project_id,
            Project.id == project_id,
            Project.tenant_id == tenant_id,
        )
        .order_by(
            EnvironmentConfigVersion.version.desc()
        )
    ).all()

    return list(versions)