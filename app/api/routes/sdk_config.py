from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies.sdk_auth import (
    authenticate_sdk_key,
)
from app.db.session import get_db
from app.models.environment import Environment
from app.models.environment_config_version import (
    EnvironmentConfigVersion,
)
from app.models.environment_sdk_key import EnvironmentSDKKey
from app.schemas.config_version import (
    SDKConfigurationResponse,
)


router = APIRouter(
    prefix="/config",
    tags=["SDK Configuration"],
)


@router.get("")
def get_sdk_configuration(
    sdk_key: Annotated[
        EnvironmentSDKKey,
        Depends(authenticate_sdk_key),
    ],
    db: Annotated[Session, Depends(get_db)],
    if_none_match: Annotated[
        str | None,
        Header(),
    ] = None,
):
    environment = db.get(
        Environment,
        sdk_key.environment_id,
    )

    if (
        environment is None
        or environment.published_version == 0
    ):
        raise HTTPException(
            status_code=404,
            detail="No published configuration found",
        )

    config_version = db.scalar(
        select(EnvironmentConfigVersion).where(
            EnvironmentConfigVersion.environment_id
            == environment.id,
            EnvironmentConfigVersion.version
            == environment.published_version,
        )
    )

    if config_version is None:
        raise HTTPException(
            status_code=404,
            detail="Published configuration not found",
        )

    etag = f'"{config_version.checksum}"'

    if if_none_match == etag:
        return Response(
            status_code=304,
            headers={"ETag": etag},
        )

    response = SDKConfigurationResponse(
        version=config_version.version,
        checksum=config_version.checksum,
        configuration=config_version.configuration,
    )

    return JSONResponse(
        content=jsonable_encoder(response),
        headers={
            "ETag": etag,
            "Cache-Control": "private, no-cache",
        },
    )