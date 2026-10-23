"""Bind new plans to immutable catalogue, slot and target inputs.

Legacy rows deliberately remain unbound; no historical authority is manufactured.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from savora_backend.database import JsonbType

revision: str = "0008_saved_plan_source_binding"
down_revision: str | None = "0007_password_reset"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("meal_plans", sa.Column("source_binding", JsonbType, nullable=True))


def downgrade() -> None:
    op.drop_column("meal_plans", "source_binding")
