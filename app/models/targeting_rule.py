import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class TargetingRule(Base):
    __tablename__ = "targeting_rules"
    # database constraints
    __table_args__ = (
        UniqueConstraint(
            "feature_flag_id",
            "priority",
            name="uq_targeting_rules_flag_priority",
        ),# 2 rules with same priority not allowed
        CheckConstraint(
            "priority >= 1",
            name="ck_targeting_rules_positive_priority",
        ),
        CheckConstraint(
            "serve_type IN ('fixed', 'percentage')",
            name="ck_targeting_rules_serve_type",
        ),
        CheckConstraint(
            """
            (
                serve_type = 'fixed'
                AND serve_value IS NOT NULL
                AND true_basis_points IS NULL
            )
            OR
            (
                serve_type = 'percentage'
                AND serve_value IS NULL
                AND true_basis_points IS NOT NULL
                AND true_basis_points BETWEEN 0 AND 10000
            )
            """,
            name="ck_targeting_rules_valid_serve",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )# automatically generated 

    feature_flag_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("feature_flags.id", ondelete="CASCADE"),
        nullable=False,
        index=True, # create additional index on this column 
    )# identifies the feature flag owning this rule

    priority: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    serve_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    serve_value: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
    )

    true_basis_points: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    feature_flag: Mapped["FeatureFlag"] = relationship(
        back_populates="rules",
    )

    conditions: Mapped[list["RuleCondition"]] = relationship(
        back_populates="rule",
        cascade="all, delete-orphan",# delete-orphan means deleting a rule will also delete all its conditions
    )
