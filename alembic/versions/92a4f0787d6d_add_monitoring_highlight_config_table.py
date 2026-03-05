"""add_monitoring_highlight_config_table

Revision ID: 92a4f0787d6d
Revises: 47d5aa21b5f1
Create Date: 2026-03-02 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "92a4f0787d6d"
down_revision: Union[str, Sequence[str], None] = "47d5aa21b5f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return table_name in inspector.get_table_names()


def _index_exists(table_name: str, index_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(index["name"] == index_name for index in inspector.get_indexes(table_name))


def upgrade() -> None:
    if not _table_exists("monitoring_highlight_config"):
        op.create_table(
            "monitoring_highlight_config",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column(
                "is_active",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("true"),
            ),
            sa.Column(
                "frustration_min_threshold",
                sa.SmallInteger(),
                nullable=False,
                server_default=sa.text("7"),
            ),
            sa.Column(
                "failure_escalation_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("true"),
            ),
            sa.Column(
                "loop_detected_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("true"),
            ),
            sa.Column(
                "accuracy_max_threshold",
                sa.SmallInteger(),
                nullable=False,
                server_default=sa.text("3"),
            ),
            sa.Column(
                "unresolved_low_satisfaction_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("true"),
            ),
            sa.Column(
                "unresolved_satisfaction_max_threshold",
                sa.SmallInteger(),
                nullable=False,
                server_default=sa.text("3"),
            ),
            sa.Column(
                "user_irrelevancy_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("true"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=False),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.CheckConstraint(
                "frustration_min_threshold BETWEEN 1 AND 10",
                name="ck_monitoring_highlight_config_frustration_min_threshold_range",
            ),
            sa.CheckConstraint(
                "accuracy_max_threshold BETWEEN 1 AND 10",
                name="ck_monitoring_highlight_config_accuracy_max_threshold_range",
            ),
            sa.CheckConstraint(
                "unresolved_satisfaction_max_threshold BETWEEN 1 AND 10",
                name="ck_monitoring_highlight_config_unresolved_satisfaction_max_threshold_range",
            ),
            sa.PrimaryKeyConstraint("id", name="pk_monitoring_highlight_config"),
        )

    if not _index_exists(
        "monitoring_highlight_config",
        "uq_monitoring_highlight_config_single_active",
    ):
        op.create_index(
            "uq_monitoring_highlight_config_single_active",
            "monitoring_highlight_config",
            ["is_active"],
            unique=True,
            postgresql_where=sa.text("is_active"),
        )

    op.execute(
        sa.text(
            """
            INSERT INTO monitoring_highlight_config (
                is_active,
                frustration_min_threshold,
                failure_escalation_enabled,
                loop_detected_enabled,
                accuracy_max_threshold,
                unresolved_low_satisfaction_enabled,
                unresolved_satisfaction_max_threshold,
                user_irrelevancy_enabled,
                updated_at
            )
            SELECT
                true,
                7,
                true,
                true,
                3,
                true,
                3,
                true,
                CURRENT_TIMESTAMP
            WHERE NOT EXISTS (
                SELECT 1
                FROM monitoring_highlight_config
                WHERE is_active = true
            )
            """
        )
    )


def downgrade() -> None:
    if not _table_exists("monitoring_highlight_config"):
        return

    if _index_exists(
        "monitoring_highlight_config",
        "uq_monitoring_highlight_config_single_active",
    ):
        op.drop_index(
            "uq_monitoring_highlight_config_single_active",
            table_name="monitoring_highlight_config",
        )

    op.drop_table("monitoring_highlight_config")
