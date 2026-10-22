"""Create meal_plan_substitutions table.

Revision ID: 0004_create_substitutions
Revises: 0003_create_meal_plans
Create Date: 2026-10-20 23:25:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from savora_backend.database import JsonbType, StringArrayType

revision: str = "0004_create_substitutions"
down_revision: str | None = "0003_create_meal_plans"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "meal_plan_substitutions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("from_plan_id", sa.Uuid(), nullable=False),
        sa.Column("to_plan_id", sa.Uuid(), nullable=True),
        sa.Column("slot_id", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="GENERATING"),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("before_snapshot", JsonbType, nullable=True),
        sa.Column("after_snapshot", JsonbType, nullable=True),
        sa.Column("excluded_combination_ids", StringArrayType, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["from_plan_id"], ["meal_plans.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["to_plan_id"], ["meal_plans.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_meal_plan_substitutions_user_id",
        "meal_plan_substitutions",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_meal_plan_substitutions_from_plan_id",
        "meal_plan_substitutions",
        ["from_plan_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_meal_plan_substitutions_from_plan_id", table_name="meal_plan_substitutions"
    )
    op.drop_index(
        "ix_meal_plan_substitutions_user_id", table_name="meal_plan_substitutions"
    )
    op.drop_table("meal_plan_substitutions")
