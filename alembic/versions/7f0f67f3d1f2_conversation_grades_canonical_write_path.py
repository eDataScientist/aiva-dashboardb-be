"""conversation_grades_canonical_write_path

Revision ID: 7f0f67f3d1f2
Revises: c3a1f82d9b55
Create Date: 2026-03-09 07:45:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "7f0f67f3d1f2"
down_revision: Union[str, Sequence[str], None] = "c3a1f82d9b55"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return table_name in inspector.get_table_names()


def _index_exists(table_name: str, index_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(index["name"] == index_name for index in inspector.get_indexes(table_name))


def upgrade() -> None:
    if not _table_exists("conversation_grades"):
        return

    op.execute(
        """
        UPDATE conversation_grades
        SET identity_type = 'phone',
            conversation_identity = phone_number
        WHERE phone_number IS NOT NULL
          AND (identity_type IS NULL OR conversation_identity IS NULL)
        """
    )

    op.alter_column(
        "conversation_grades",
        "phone_number",
        existing_type=sa.String(length=64),
        nullable=True,
    )

    if not _index_exists("conversation_grades", "uq_conversation_grades_identity_day"):
        op.create_index(
            "uq_conversation_grades_identity_day",
            "conversation_grades",
            ["identity_type", "conversation_identity", "grade_date"],
            unique=True,
            postgresql_where=sa.text(
                "identity_type IS NOT NULL AND conversation_identity IS NOT NULL"
            ),
        )


def downgrade() -> None:
    if not _table_exists("conversation_grades"):
        return

    if _index_exists("conversation_grades", "uq_conversation_grades_identity_day"):
        op.drop_index(
            "uq_conversation_grades_identity_day",
            table_name="conversation_grades",
        )

    op.execute(
        """
        UPDATE conversation_grades
        SET phone_number = conversation_identity
        WHERE phone_number IS NULL
          AND conversation_identity IS NOT NULL
        """
    )

    op.alter_column(
        "conversation_grades",
        "phone_number",
        existing_type=sa.String(length=64),
        nullable=False,
    )
