from typing import Annotated
from dataclasses import dataclass
import uuid
from fastapi import Depends, HTTPException, status
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
)
from sqlalchemy.orm import Session

from app.db.session import get_db, SessionLocal
from app.models.environment_sdk_key import EnvironmentSDKKey
from app.security.sdk_keys import (
    extract_key_id,
    verify_sdk_key,
)


bearer_scheme = HTTPBearer(auto_error=False)

@dataclass(frozen=True)
class SDKPrincipal:
    key_id: uuid.UUID
    environment_id: uuid.UUID


def authenticate_sdk_key(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
) -> SDKPrincipal:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="SDK key required",
        )

    plain_key = credentials.credentials
    key_id = extract_key_id(plain_key)

    if key_id is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid SDK key",
        )

    with SessionLocal() as db:
        sdk_key = db.get(
            EnvironmentSDKKey,
            key_id,
        )

        if (
            sdk_key is None
            or sdk_key.revoked_at is not None
            or not verify_sdk_key(
                plain_key,
                sdk_key.key_hash,
            )
        ):
            raise HTTPException(
                status_code=401,
                detail="Invalid or revoked SDK key",
            )

        return SDKPrincipal(
            key_id=sdk_key.id,
            environment_id=sdk_key.environment_id,
        )