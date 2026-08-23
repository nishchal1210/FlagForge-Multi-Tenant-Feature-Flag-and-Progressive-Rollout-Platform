
import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func # lets SQLAlchemy call database functions such as NOW().
from sqlalchemy.orm import Mapped, mapped_column, relationship

# Mapped: describes the Python type of a model attribute.
# mapped_column: defines a database column.
# relationship: connects this model with another model.

from app.db.base import Base


class Tenant(Base):
    __tablename__ = "tenants"


    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    projects: Mapped[list["Project"]] = relationship(
        back_populates="tenant",
        cascade="all, delete-orphan",
    )