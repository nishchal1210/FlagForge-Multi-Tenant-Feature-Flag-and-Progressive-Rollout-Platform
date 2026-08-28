import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


ConditionValue = (
    str
    | int
    | float
    | bool
    | list[str | int | float | bool]
)


class ConditionCreate(BaseModel):
    attribute: str = Field(
        min_length=1,
        max_length=100,
        pattern=r"^[a-zA-Z0-9_.-]+$",
    )

    operator: Literal[
        "equals",
        "not_equals",
        "in",
        "not_in",
    ]

    value: ConditionValue

    @model_validator(mode="after")
    def validate_operator_value(self):
        if self.operator in {"in", "not_in"}:
            if not isinstance(self.value, list):
                raise ValueError(
                    "'in' and 'not_in' require a list value"
                )

        return self


class FixedServe(BaseModel):
    type: Literal["fixed"]
    value: bool


class PercentageServe(BaseModel):
    type: Literal["percentage"]

    true_basis_points: int = Field(
        ge=0,
        le=10000,
    )


ServeConfiguration = Annotated[
    FixedServe | PercentageServe,
    Field(discriminator="type"),
]


class TargetingRuleCreate(BaseModel):
    priority: int = Field(ge=1)

    conditions: list[ConditionCreate] = Field(
        default_factory=list,
    )

    serve: ServeConfiguration


class ConditionResponse(BaseModel):
    id: uuid.UUID
    attribute: str
    operator: str
    value: ConditionValue

    model_config = ConfigDict(from_attributes=True)


class TargetingRuleResponse(BaseModel):
    id: uuid.UUID
    feature_flag_id: uuid.UUID
    priority: int
    serve_type: str
    serve_value: bool | None
    true_basis_points: int | None
    conditions: list[ConditionResponse]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)