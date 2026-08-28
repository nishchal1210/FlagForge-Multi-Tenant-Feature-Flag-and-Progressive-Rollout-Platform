"""add targeting rule tables

Revision ID: 8b17a9cf42ed
Revises: 55c438628b1d
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "8b17a9cf42ed"
down_revision: str | None = "55c438628b1d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "targeting_rules",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("feature_flag_id", sa.Uuid(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("serve_type", sa.String(length=20), nullable=False),
        sa.Column("serve_value", sa.Boolean(), nullable=True),
        sa.Column("true_basis_points", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "priority >= 1",
            name="ck_targeting_rules_positive_priority",
        ),
        sa.CheckConstraint(
            "serve_type IN ('fixed', 'percentage')",
            name="ck_targeting_rules_serve_type",
        ),
        sa.CheckConstraint(
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
        sa.ForeignKeyConstraint(
            ["feature_flag_id"],
            ["feature_flags.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "feature_flag_id",
            "priority",
            name="uq_targeting_rules_flag_priority",
        ),
    )
    op.create_index(
        op.f("ix_targeting_rules_feature_flag_id"),
        "targeting_rules",
        ["feature_flag_id"],
        unique=False,
    )

    op.create_table(
        "rule_conditions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("rule_id", sa.Uuid(), nullable=False),
        sa.Column("attribute", sa.String(length=100), nullable=False),
        sa.Column("operator", sa.String(length=20), nullable=False),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.CheckConstraint(
            "operator IN ('equals', 'not_equals', 'in', 'not_in')",
            name="ck_rule_conditions_operator",
        ),
        sa.ForeignKeyConstraint(
            ["rule_id"],
            ["targeting_rules.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_rule_conditions_rule_id"),
        "rule_conditions",
        ["rule_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_rule_conditions_rule_id"),
        table_name="rule_conditions",
    )
    op.drop_table("rule_conditions")
    op.drop_index(
        op.f("ix_targeting_rules_feature_flag_id"),
        table_name="targeting_rules",
    )
    op.drop_table("targeting_rules")
