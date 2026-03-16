"""add_phase6_monitoring_read_indexes

Revision ID: 9e8a6f7c1d2b
Revises: 5c8324f8b9a1
Create Date: 2026-03-16 18:10:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "9e8a6f7c1d2b"
down_revision: Union[str, Sequence[str], None] = "5c8324f8b9a1"
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

    for index_name, columns in (
        (
            "ix_conversation_grades_grade_date_resolution",
            ["grade_date", "resolution"],
        ),
        (
            "ix_conversation_grades_grade_date_frustration_score",
            ["grade_date", "frustration_score"],
        ),
        (
            "ix_conversation_grades_grade_date_accuracy_score",
            ["grade_date", "accuracy_score"],
        ),
    ):
        if not _index_exists("conversation_grades", index_name):
            op.create_index(index_name, "conversation_grades", columns, unique=False)


def downgrade() -> None:
    if not _table_exists("conversation_grades"):
        return

    for index_name in (
        "ix_conversation_grades_grade_date_accuracy_score",
        "ix_conversation_grades_grade_date_frustration_score",
        "ix_conversation_grades_grade_date_resolution",
    ):
        if _index_exists("conversation_grades", index_name):
            op.drop_index(index_name, table_name="conversation_grades")
