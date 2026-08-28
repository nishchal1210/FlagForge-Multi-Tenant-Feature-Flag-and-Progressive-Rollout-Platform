from typing import Any

from pydantic import BaseModel, Field, model_validator


class EvaluationRequest(BaseModel):
    user: dict[str, Any]

    @model_validator(mode="after")
    def validate_user_key(self):
        key = self.user.get("key")

        if not isinstance(key, str) or not key:
            raise ValueError(
                "user.key must be a non-empty string"
            )

        return self


class EvaluationResponse(BaseModel):
    flag_key: str
    value: bool
    reason: str
    matched_rule_priority: int | None = None
    bucket: int | None = Field(
        default=None,
        ge=0,
        le=9999,
    )
