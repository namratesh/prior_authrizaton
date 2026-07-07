"""add case_number

Revision ID: c1a2b3d4e5f6
Revises: 99046c042b17
Create Date: 2026-07-07 03:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c1a2b3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '99046c042b17'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Human-readable sequential case numbers (PA-<year>-<seq>) layered on
    top of the UUID primary key, which stays the real identifier for
    routing/joins."""
    op.add_column(
        "cases",
        sa.Column(
            "case_number",
            sa.Integer(),
            sa.Identity(always=False),
            nullable=False,
        ),
    )
    op.create_unique_constraint("uq_cases_case_number", "cases", ["case_number"])


def downgrade() -> None:
    op.drop_constraint("uq_cases_case_number", "cases", type_="unique")
    op.drop_column("cases", "case_number")
