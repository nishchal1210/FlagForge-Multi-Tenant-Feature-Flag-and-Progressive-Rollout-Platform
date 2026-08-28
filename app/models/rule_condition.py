import uuid
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    JSON,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class RuleCondition(Base):
    __tablename__ = "rule_conditions"

    __table_args__ = (
        CheckConstraint(
            """
            operator IN (
                'equals',
                'not_equals',
                'in',
                'not_in'
            )
            """,
            name="ck_rule_conditions_operator",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )

    rule_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("targeting_rules.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    attribute: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    operator: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    value: Mapped[Any] = mapped_column(
        JSON,
        nullable=False,
    )

    rule: Mapped["TargetingRule"] = relationship(
        back_populates="conditions",
    )
