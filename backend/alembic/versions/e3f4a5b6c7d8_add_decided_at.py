"""add decided_at to cases

Revision ID: e3f4a5b6c7d8
Revises: d2e3f4a5b6c7
Create Date: 2026-07-07 05:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'e3f4a5b6c7d8'
down_revision: Union[str, Sequence[str], None] = 'd2e3f4a5b6c7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # updated_at is bumped on every graph step (intake, cost, rag, ...), not
    # just at finalization, so it can't be used to bucket "when was this case
    # decided" for the accuracy-drift chart. decided_at is set exactly once,
    # the moment final_status first becomes non-null.
    op.add_column("cases", sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True))
    op.execute("UPDATE cases SET decided_at = updated_at WHERE final_status IS NOT NULL")


def downgrade() -> None:
    op.drop_column("cases", "decided_at")
