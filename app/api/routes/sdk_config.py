from typing import Annotated
import asyncio
import json
from fastapi.responses import StreamingResponse

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies.sdk_auth import (
    SDKPrincipal,
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
from app.realtime.connection_manager import (
    sse_manager,
)


router = APIRouter(
    prefix="/config",
    tags=["SDK Configuration"],
)

@router.get("/stream")
async def stream_configuration_updates(
    sdk_principal: Annotated[
        SDKPrincipal,
        Depends(authenticate_sdk_key),
    ],
):
    environment_id = str(
        sdk_principal.environment_id
    )

    queue = await sse_manager.connect(
        environment_id
    )

    async def event_generator():
        try:
            connected_event = {
                "type": "connected",
                "environment_id": environment_id,
            }

            yield (
                "event: connected\n"
                f"data: {json.dumps(connected_event)}\n\n"
            )

            while True:
                try:
                    event = await asyncio.wait_for(
                        queue.get(),
                        timeout=15,
                    )

                    yield (
                        "event: config_updated\n"
                        f"id: {event['version']}\n"
                        f"data: {json.dumps(event)}\n\n"
                    )

                except TimeoutError:
                    yield ": keep-alive\n\n"

        finally:
            await sse_manager.disconnect(
                environment_id,
                queue,
            )

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
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