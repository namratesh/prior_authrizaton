"""add overcharge_threshold_percent to admin_settings

Revision ID: f4a5b6c7d8e9
Revises: e3f4a5b6c7d8
Create Date: 2026-07-07 06:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'f4a5b6c7d8e9'
down_revision: Union[str, Sequence[str], None] = 'e3f4a5b6c7d8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Generalizes cost_agent.py's OVERCHARGE_THRESHOLD_PERCENT hardcoded
    # constant into the same admin-tunable settings row as sla_hours /
    # expedite_hours / confidence_threshold.
    op.add_column(
        "admin_settings",
        sa.Column("overcharge_threshold_percent", sa.Float(), nullable=False, server_default="20.0"),
    )
    op.alter_column("admin_settings", "overcharge_threshold_percent", server_default=None)


def downgrade() -> None:
    op.drop_column("admin_settings", "overcharge_threshold_percent")
