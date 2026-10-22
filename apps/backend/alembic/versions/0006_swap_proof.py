"""Record Member 2's compact B1 swap proof on each substitution.

Revision ID: 0006_swap_proof
Revises: 0005_swap_choice_and_job_guards
Create Date: 2026-10-23 09:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from savora_backend.database import JsonbType

revision: str = "0006_swap_proof"
down_revision: str | None = "0005_swap_choice_and_job_guards"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "meal_plan_substitutions",
        sa.Column("proof_certificate_digest", sa.String(length=64), nullable=True),
    )
    op.add_column("meal_plan_substitutions", sa.Column("proof", JsonbType, nullable=True))


def downgrade() -> None:
    op.drop_column("meal_plan_substitutions", "proof")
    op.drop_column("meal_plan_substitutions", "proof_certificate_digest")
