"""add case assignment + admin settings table

Revision ID: d2e3f4a5b6c7
Revises: c1a2b3d4e5f6
Create Date: 2026-07-07 04:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'd2e3f4a5b6c7'
down_revision: Union[str, Sequence[str], None] = 'c1a2b3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("cases", sa.Column("assigned_to", sa.String(length=36), nullable=True))
    op.add_column("cases", sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index(op.f("ix_cases_assigned_to"), "cases", ["assigned_to"], unique=False)

    op.create_table(
        "admin_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("sla_hours", sa.Float(), nullable=False),
        sa.Column("expedite_hours", sa.Float(), nullable=False),
        sa.Column("confidence_threshold", sa.Float(), nullable=False),
        sa.Column("agents_enabled", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    # Single-row table (id is always 1) — seed the defaults that were
    # previously hardcoded constants in supervisor.py / peer_review_agent.py.
    op.execute(
        """
        INSERT INTO admin_settings (id, sla_hours, expedite_hours, confidence_threshold, agents_enabled, updated_at)
        VALUES (1, 48.0, 2.0, 0.85, '{"cost": true, "rag": true, "alternative": true}', now())
        """
    )


def downgrade() -> None:
    op.drop_table("admin_settings")
    op.drop_index(op.f("ix_cases_assigned_to"), table_name="cases")
    op.drop_column("cases", "assigned_at")
    op.drop_column("cases", "assigned_to")
