"""add_grading_run_tables

Revision ID: b2f9b9d5d40e
Revises: 7f0f67f3d1f2
Create Date: 2026-03-11 15:55:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "b2f9b9d5d40e"
down_revision: Union[str, Sequence[str], None] = "7f0f67f3d1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return table_name in inspector.get_table_names()


def _index_exists(table_name: str, index_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(index["name"] == index_name for index in inspector.get_indexes(table_name))


def upgrade() -> None:
    if not _table_exists("grading_runs"):
        op.create_table(
            "grading_runs",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("trigger_type", sa.String(length=16), nullable=False),
            sa.Column("run_mode", sa.String(length=16), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("target_start_date", sa.Date(), nullable=False),
            sa.Column("target_end_date", sa.Date(), nullable=False),
            sa.Column(
                "rerun_existing",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
            sa.Column("provider", sa.String(length=64), nullable=False),
            sa.Column("model", sa.String(length=128), nullable=False),
            sa.Column("prompt_version", sa.String(length=64), nullable=False),
            sa.Column(
                "candidate_count",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("0"),
            ),
            sa.Column(
                "attempted_count",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("0"),
            ),
            sa.Column(
                "success_count",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("0"),
            ),
            sa.Column(
                "skipped_existing_count",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("0"),
            ),
            sa.Column(
                "empty_transcript_count",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("0"),
            ),
            sa.Column(
                "provider_error_count",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("0"),
            ),
            sa.Column(
                "parse_error_count",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("0"),
            ),
            sa.Column("requested_by_account_id", sa.Uuid(), nullable=True),
            sa.Column("error_message", sa.String(length=500), nullable=True),
            sa.Column("started_at", sa.DateTime(timezone=False), nullable=True),
            sa.Column("finished_at", sa.DateTime(timezone=False), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=False),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=False),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.CheckConstraint(
                "trigger_type IN ('scheduled', 'manual')",
                name="ck_grading_runs_trigger_type_values",
            ),
            sa.CheckConstraint(
                "run_mode IN ('daily', 'backfill', 'rerun')",
                name="ck_grading_runs_run_mode_values",
            ),
            sa.CheckConstraint(
                "status IN ('queued', 'running', 'completed', "
                "'completed_with_failures', 'failed')",
                name="ck_grading_runs_status_values",
            ),
            sa.CheckConstraint(
                "target_start_date <= target_end_date",
                name="ck_grading_runs_target_window_order",
            ),
            sa.CheckConstraint(
                "candidate_count >= 0",
                name="ck_grading_runs_candidate_count_non_negative",
            ),
            sa.CheckConstraint(
                "attempted_count >= 0",
                name="ck_grading_runs_attempted_count_non_negative",
            ),
            sa.CheckConstraint(
                "success_count >= 0",
                name="ck_grading_runs_success_count_non_negative",
            ),
            sa.CheckConstraint(
                "skipped_existing_count >= 0",
                name="ck_grading_runs_skipped_existing_count_non_negative",
            ),
            sa.CheckConstraint(
                "empty_transcript_count >= 0",
                name="ck_grading_runs_empty_transcript_count_non_negative",
            ),
            sa.CheckConstraint(
                "provider_error_count >= 0",
                name="ck_grading_runs_provider_error_count_non_negative",
            ),
            sa.CheckConstraint(
                "parse_error_count >= 0",
                name="ck_grading_runs_parse_error_count_non_negative",
            ),
            sa.ForeignKeyConstraint(
                ["requested_by_account_id"],
                ["accounts.id"],
                name="fk_grading_runs_requested_by_account_id_accounts",
                ondelete="SET NULL",
            ),
            sa.PrimaryKeyConstraint("id", name="pk_grading_runs"),
        )

    if not _index_exists("grading_runs", "ix_grading_runs_status_created_at"):
        op.create_index(
            "ix_grading_runs_status_created_at",
            "grading_runs",
            ["status", "created_at"],
            unique=False,
        )
    if not _index_exists("grading_runs", "ix_grading_runs_target_window_status"):
        op.create_index(
            "ix_grading_runs_target_window_status",
            "grading_runs",
            ["target_start_date", "target_end_date", "status"],
            unique=False,
        )
    if not _index_exists("grading_runs", "ix_grading_runs_requested_by_account_id"):
        op.create_index(
            "ix_grading_runs_requested_by_account_id",
            "grading_runs",
            ["requested_by_account_id"],
            unique=False,
        )

    if not _table_exists("grading_run_items"):
        op.create_table(
            "grading_run_items",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("run_id", sa.Uuid(), nullable=False),
            sa.Column("identity_type", sa.String(length=16), nullable=False),
            sa.Column("conversation_identity", sa.String(length=255), nullable=False),
            sa.Column("grade_date", sa.Date(), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("grade_id", sa.Uuid(), nullable=True),
            sa.Column("error_message", sa.String(length=500), nullable=True),
            sa.Column("error_details", sa.JSON(), nullable=True),
            sa.Column("started_at", sa.DateTime(timezone=False), nullable=True),
            sa.Column("finished_at", sa.DateTime(timezone=False), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=False),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=False),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.CheckConstraint(
                "identity_type IN ('phone', 'email', 'session')",
                name="ck_grading_run_items_identity_type_values",
            ),
            sa.CheckConstraint(
                "status IN ('success', 'skipped_existing', 'empty_transcript', "
                "'provider_error', 'parse_error')",
                name="ck_grading_run_items_status_values",
            ),
            sa.ForeignKeyConstraint(
                ["grade_id"],
                ["conversation_grades.id"],
                name="fk_grading_run_items_grade_id_conversation_grades",
                ondelete="SET NULL",
            ),
            sa.ForeignKeyConstraint(
                ["run_id"],
                ["grading_runs.id"],
                name="fk_grading_run_items_run_id_grading_runs",
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id", name="pk_grading_run_items"),
            sa.UniqueConstraint(
                "run_id",
                "identity_type",
                "conversation_identity",
                "grade_date",
                name="uq_grading_run_items_run_candidate",
            ),
        )

    if not _index_exists("grading_run_items", "ix_grading_run_items_run_id_status"):
        op.create_index(
            "ix_grading_run_items_run_id_status",
            "grading_run_items",
            ["run_id", "status"],
            unique=False,
        )
    if not _index_exists("grading_run_items", "ix_grading_run_items_run_id_grade_date"):
        op.create_index(
            "ix_grading_run_items_run_id_grade_date",
            "grading_run_items",
            ["run_id", "grade_date"],
            unique=False,
        )
    if not _index_exists("grading_run_items", "ix_grading_run_items_grade_id"):
        op.create_index(
            "ix_grading_run_items_grade_id",
            "grading_run_items",
            ["grade_id"],
            unique=False,
        )


def downgrade() -> None:
    if _table_exists("grading_run_items"):
        if _index_exists("grading_run_items", "ix_grading_run_items_grade_id"):
            op.drop_index("ix_grading_run_items_grade_id", table_name="grading_run_items")
        if _index_exists("grading_run_items", "ix_grading_run_items_run_id_grade_date"):
            op.drop_index(
                "ix_grading_run_items_run_id_grade_date",
                table_name="grading_run_items",
            )
        if _index_exists("grading_run_items", "ix_grading_run_items_run_id_status"):
            op.drop_index(
                "ix_grading_run_items_run_id_status",
                table_name="grading_run_items",
            )
        op.drop_table("grading_run_items")

    if _table_exists("grading_runs"):
        if _index_exists("grading_runs", "ix_grading_runs_requested_by_account_id"):
            op.drop_index(
                "ix_grading_runs_requested_by_account_id",
                table_name="grading_runs",
            )
        if _index_exists("grading_runs", "ix_grading_runs_target_window_status"):
            op.drop_index(
                "ix_grading_runs_target_window_status",
                table_name="grading_runs",
            )
        if _index_exists("grading_runs", "ix_grading_runs_status_created_at"):
            op.drop_index(
                "ix_grading_runs_status_created_at",
                table_name="grading_runs",
            )
        op.drop_table("grading_runs")
