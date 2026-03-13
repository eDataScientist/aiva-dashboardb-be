"""add_phase5_metrics_read_indexes

Revision ID: 5c8324f8b9a1
Revises: b2f9b9d5d40e
Create Date: 2026-03-13 11:35:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "5c8324f8b9a1"
down_revision: Union[str, Sequence[str], None] = "b2f9b9d5d40e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return table_name in inspector.get_table_names()


def _index_exists(table_name: str, index_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(index["name"] == index_name for index in inspector.get_indexes(table_name))


def upgrade() -> None:
    if _table_exists("conversation_grades"):
        if not _index_exists(
            "conversation_grades",
            "ix_conversation_grades_grade_date_intent_code",
        ):
            op.create_index(
                "ix_conversation_grades_grade_date_intent_code",
                "conversation_grades",
                ["grade_date", "intent_code"],
                unique=False,
            )
        if not _index_exists(
            "conversation_grades",
            "ix_conversation_grades_grade_date_escalation_type",
        ):
            op.create_index(
                "ix_conversation_grades_grade_date_escalation_type",
                "conversation_grades",
                ["grade_date", "escalation_type"],
                unique=False,
            )

    if _table_exists("grading_runs") and not _index_exists(
        "grading_runs",
        "ix_grading_runs_successful_finished_at",
    ):
        op.create_index(
            "ix_grading_runs_successful_finished_at",
            "grading_runs",
            ["finished_at", "created_at"],
            unique=False,
            postgresql_where=sa.text(
                "status IN ('completed', 'completed_with_failures')"
            ),
        )


def downgrade() -> None:
    if _table_exists("grading_runs") and _index_exists(
        "grading_runs",
        "ix_grading_runs_successful_finished_at",
    ):
        op.drop_index(
            "ix_grading_runs_successful_finished_at",
            table_name="grading_runs",
        )

    if _table_exists("conversation_grades"):
        if _index_exists(
            "conversation_grades",
            "ix_conversation_grades_grade_date_escalation_type",
        ):
            op.drop_index(
                "ix_conversation_grades_grade_date_escalation_type",
                table_name="conversation_grades",
            )
        if _index_exists(
            "conversation_grades",
            "ix_conversation_grades_grade_date_intent_code",
        ):
            op.drop_index(
                "ix_conversation_grades_grade_date_intent_code",
                table_name="conversation_grades",
            )
