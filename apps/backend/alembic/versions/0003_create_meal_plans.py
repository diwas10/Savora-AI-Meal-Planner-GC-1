"""Create meal_plans and meal_plan_slots tables.

Revision ID: 0003_create_meal_plans
Revises: 0002_create_profiles_and_targets
Create Date: 2026-10-20 23:15:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from savora_backend.database import JsonbType

revision: str = "0003_create_meal_plans"
down_revision: str | None = "0002_create_profiles_and_targets"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "meal_plans",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="GENERATING"),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("profile_version", sa.Integer(), nullable=False),
        sa.Column("catalogue_version", sa.String(length=64), nullable=True),
        sa.Column("model_version", sa.String(length=64), nullable=True),
        sa.Column("fallback_reason", sa.String(length=64), nullable=True),
        sa.Column("kb_id", sa.String(length=64), nullable=True),
        sa.Column("kb_version", sa.String(length=64), nullable=True),
        sa.Column("safety", JsonbType, nullable=True),
        sa.Column("search", JsonbType, nullable=True),
        sa.Column("day_totals", JsonbType, nullable=True),
        sa.Column("parent_plan_id", sa.Uuid(), nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["parent_plan_id"], ["meal_plans.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_meal_plans_user_current",
        "meal_plans",
        ["user_id", "is_current"],
        unique=False,
    )
    op.create_index(
        "ix_meal_plans_user_week_start",
        "meal_plans",
        ["user_id", "week_start"],
        unique=False,
    )

    op.create_table(
        "meal_plan_slots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("plan_id", sa.Uuid(), nullable=False),
        sa.Column("slot_id", sa.String(length=32), nullable=False),
        sa.Column("day_index", sa.Integer(), nullable=False),
        sa.Column("calendar_date", sa.String(length=16), nullable=False),
        sa.Column("meal_type", sa.String(length=16), nullable=False),
        sa.Column("option_id", sa.String(length=255), nullable=False),
        sa.Column("combination_id", sa.String(length=255), nullable=False),
        sa.Column("configuration_id", sa.String(length=255), nullable=False),
        sa.Column("preset", sa.String(length=32), nullable=False),
        sa.Column("snapshot", JsonbType, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["plan_id"], ["meal_plans.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plan_id", "slot_id", name="uq_meal_plan_slots_plan_slot"),
    )
    op.create_index(
        "ix_meal_plan_slots_plan_id",
        "meal_plan_slots",
        ["plan_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_meal_plan_slots_plan_id", table_name="meal_plan_slots")
    op.drop_table("meal_plan_slots")
    op.drop_index("ix_meal_plans_user_week_start", table_name="meal_plans")
    op.drop_index("ix_meal_plans_user_current", table_name="meal_plans")
    op.drop_table("meal_plans")
