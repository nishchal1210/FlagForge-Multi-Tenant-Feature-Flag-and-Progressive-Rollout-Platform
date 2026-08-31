import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class EnvironmentConfigVersion(Base):
    __tablename__ = "environment_config_versions"

    __table_args__ = (
        UniqueConstraint(
            "environment_id",
            "version",
            name="uq_environment_config_version",
        ),
        CheckConstraint(
            "version >= 1",
            name="ck_environment_config_positive_version",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )

    environment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(
            "environments.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    configuration: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
    )

    checksum: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    environment: Mapped["Environment"] = relationship(
        back_populates="config_versions",
    )