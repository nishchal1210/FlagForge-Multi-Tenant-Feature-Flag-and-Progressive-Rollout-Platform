"""add environment SDK keys

Revision ID: c3a91e54b820
Revises: a585a1614f6a
Create Date: 2026-08-31
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c3a91e54b820"
down_revision: Union[str, Sequence[str], None] = "a585a1614f6a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "environment_sdk_keys",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("environment_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["environment_id"], ["environments.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key_hash"),
        sa.UniqueConstraint(
            "environment_id", "name", name="uq_environment_sdk_key_name"
        ),
    )
    op.create_index(
        op.f("ix_environment_sdk_keys_environment_id"),
        "environment_sdk_keys",
        ["environment_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_environment_sdk_keys_environment_id"),
        table_name="environment_sdk_keys",
    )
    op.drop_table("environment_sdk_keys")
