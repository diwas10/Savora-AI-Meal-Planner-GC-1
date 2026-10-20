"""Create user_profiles and user_nutrition_profiles tables.

Revision ID: 0002_create_profiles_and_targets
Revises: 0001_create_users
Create Date: 2026-10-20 22:55:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from savora_backend.database import JsonbType, StringArrayType

revision: str = "0002_create_profiles_and_targets"
down_revision: str | None = "0001_create_users"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_profiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("age_years", sa.Integer(), nullable=False),
        sa.Column("sex", sa.String(length=16), nullable=False),
        sa.Column("height_cm", sa.Float(), nullable=False),
        sa.Column("weight_kg", sa.Float(), nullable=False),
        sa.Column("activity", sa.String(length=32), nullable=False),
        sa.Column("goal", sa.String(length=32), nullable=False),
        sa.Column("diet", sa.String(length=32), nullable=True),
        sa.Column("cuisine_policy", sa.String(length=32), nullable=False, server_default="MIXED"),
        sa.Column("cuisines", StringArrayType(), nullable=False),
        sa.Column("excluded_ingredients", StringArrayType(), nullable=False),
        sa.Column("allergies", StringArrayType(), nullable=False),
        sa.Column("allergies_confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("conditions", StringArrayType(), nullable=False),
        sa.Column("seed_recipe_ids", StringArrayType(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_user_profiles_user_id"),
    )
    op.create_index("ix_user_profiles_user_id", "user_profiles", ["user_id"], unique=True)

    op.create_table(
        "user_nutrition_profiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("profile_version", sa.Integer(), nullable=False),
        sa.Column("formula_version", sa.String(length=64), nullable=False),
        sa.Column("input_hash", sa.String(length=64), nullable=False),
        sa.Column("targets", JsonbType, nullable=False),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "profile_version",
            name="uq_user_nutrition_profiles_user_version",
        ),
    )
    op.create_index(
        "ix_user_nutrition_profiles_user_id",
        "user_nutrition_profiles",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_user_nutrition_profiles_user_id", table_name="user_nutrition_profiles")
    op.drop_table("user_nutrition_profiles")
    op.drop_index("ix_user_profiles_user_id", table_name="user_profiles")
    op.drop_table("user_profiles")
