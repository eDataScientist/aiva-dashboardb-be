"""baseline_schema

Revision ID: aaa9a27982e4
Revises: 
Create Date: 2026-02-20 23:16:30.458032

"""
from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = 'aaa9a27982e4'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Baseline is intentionally non-destructive and non-creating.
    # Existing databases should be stamped to this revision, not altered.
    pass


def downgrade() -> None:
    # Baseline downgrade is also a no-op to avoid destructive behavior on legacy tables.
    pass
