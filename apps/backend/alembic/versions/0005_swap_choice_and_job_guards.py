"""Store the chosen replacement and parsed preference; one generating job per user.

Revision ID: 0005_swap_choice_and_job_guards
Revises: 0004_create_substitutions
Create Date: 2026-10-21 18:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from savora_backend.database import JsonbType

revision: str = "0005_swap_choice_and_job_guards"
down_revision: str | None = "0004_create_substitutions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

GENERATING = sa.text("status = 'GENERATING'")


def upgrade() -> None:
    op.add_column(
        "meal_plan_substitutions",
        sa.Column("replacement_combination_id", sa.String(length=255), nullable=True),
    )
    op.add_column("meal_plan_substitutions", sa.Column("preference", JsonbType, nullable=True))
    # Rows left GENERATING by an older build would block the unique indexes below.
    op.execute(
        "UPDATE meal_plans SET status = 'FAILED', message = 'Interrupted by an upgrade' "
        "WHERE status = 'GENERATING'"
    )
    op.execute(
        "UPDATE meal_plan_substitutions SET status = 'FAILED', "
        "message = 'Interrupted by an upgrade' WHERE status = 'GENERATING'"
    )
    op.create_index(
        "uq_meal_plans_user_generating",
        "meal_plans",
        ["user_id"],
        unique=True,
        postgresql_where=GENERATING,
        sqlite_where=GENERATING,
    )
    op.create_index(
        "uq_meal_plan_substitutions_user_generating",
        "meal_plan_substitutions",
        ["user_id"],
        unique=True,
        postgresql_where=GENERATING,
        sqlite_where=GENERATING,
    )


def downgrade() -> None:
    op.drop_index(
        "uq_meal_plan_substitutions_user_generating", table_name="meal_plan_substitutions"
    )
    op.drop_index("uq_meal_plans_user_generating", table_name="meal_plans")
    op.drop_column("meal_plan_substitutions", "preference")
    op.drop_column("meal_plan_substitutions", "replacement_combination_id")
