
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func, Integer, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from feature_flag import FeatureFlag
from project import Project
from environment_sdk_key import EnvironmentSDKKey
from environment_config_version import EnvironmentConfigVersion
from app.db.base import Base


class Environment(Base):
    __tablename__ = "environments"

    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "key",
            name="uq_environments_project_key",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )


    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    published_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )

    project: Mapped["Project"] = relationship(
        back_populates="environments",
    )

    flags: Mapped[list["FeatureFlag"]] = relationship(
        back_populates="environment",
        cascade="all, delete-orphan",
    )

    config_versions: Mapped[list["EnvironmentConfigVersion"]] = relationship(
        back_populates="environment",
        cascade="all, delete-orphan",
        order_by="EnvironmentConfigVersion.version",
    )

    sdk_keys: Mapped[list["EnvironmentSDKKey"]] = relationship(
        back_populates="environment",
        cascade="all, delete-orphan",
    )