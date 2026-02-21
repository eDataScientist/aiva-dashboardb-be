"""analytics_extension

Revision ID: 8c17673a6641
Revises: aaa9a27982e4
Create Date: 2026-02-20 23:26:37.187159

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8c17673a6641'
down_revision: Union[str, Sequence[str], None] = 'aaa9a27982e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def _table_exists(table_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    if _table_exists("conversation_grades"):
        return

    op.create_table(
        "conversation_grades",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("phone_number", sa.String(length=64), nullable=False),
        sa.Column("grade_date", sa.Date(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=False),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("relevancy_score", sa.SmallInteger(), nullable=True),
        sa.Column("relevancy_reasoning", sa.Text(), nullable=True),
        sa.Column("accuracy_score", sa.SmallInteger(), nullable=True),
        sa.Column("accuracy_reasoning", sa.Text(), nullable=True),
        sa.Column("completeness_score", sa.SmallInteger(), nullable=True),
        sa.Column("completeness_reasoning", sa.Text(), nullable=True),
        sa.Column("clarity_score", sa.SmallInteger(), nullable=True),
        sa.Column("clarity_reasoning", sa.Text(), nullable=True),
        sa.Column("tone_score", sa.SmallInteger(), nullable=True),
        sa.Column("tone_reasoning", sa.Text(), nullable=True),
        sa.Column("resolution", sa.Boolean(), nullable=True),
        sa.Column("resolution_reasoning", sa.Text(), nullable=True),
        sa.Column("repetition_score", sa.SmallInteger(), nullable=True),
        sa.Column("repetition_reasoning", sa.Text(), nullable=True),
        sa.Column("loop_detected", sa.Boolean(), nullable=True),
        sa.Column("loop_detected_reasoning", sa.Text(), nullable=True),
        sa.Column("satisfaction_score", sa.SmallInteger(), nullable=True),
        sa.Column("satisfaction_reasoning", sa.Text(), nullable=True),
        sa.Column("frustration_score", sa.SmallInteger(), nullable=True),
        sa.Column("frustration_reasoning", sa.Text(), nullable=True),
        sa.Column("user_relevancy", sa.Boolean(), nullable=True),
        sa.Column("user_relevancy_reasoning", sa.Text(), nullable=True),
        sa.Column("escalation_occurred", sa.Boolean(), nullable=True),
        sa.Column("escalation_occurred_reasoning", sa.Text(), nullable=True),
        sa.Column("escalation_type", sa.String(length=32), nullable=True),
        sa.Column("escalation_type_reasoning", sa.Text(), nullable=True),
        sa.Column("intent_label", sa.String(length=255), nullable=True),
        sa.Column("intent_reasoning", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "phone_number",
            "grade_date",
            name="uq_conversation_grades_phone_number_grade_date",
        ),
        sa.CheckConstraint(
            "(relevancy_score BETWEEN 1 AND 10) OR relevancy_score IS NULL",
            name="ck_conversation_grades_relevancy_score_range",
        ),
        sa.CheckConstraint(
            "(accuracy_score BETWEEN 1 AND 10) OR accuracy_score IS NULL",
            name="ck_conversation_grades_accuracy_score_range",
        ),
        sa.CheckConstraint(
            "(completeness_score BETWEEN 1 AND 10) OR completeness_score IS NULL",
            name="ck_conversation_grades_completeness_score_range",
        ),
        sa.CheckConstraint(
            "(clarity_score BETWEEN 1 AND 10) OR clarity_score IS NULL",
            name="ck_conversation_grades_clarity_score_range",
        ),
        sa.CheckConstraint(
            "(tone_score BETWEEN 1 AND 10) OR tone_score IS NULL",
            name="ck_conversation_grades_tone_score_range",
        ),
        sa.CheckConstraint(
            "(repetition_score BETWEEN 1 AND 10) OR repetition_score IS NULL",
            name="ck_conversation_grades_repetition_score_range",
        ),
        sa.CheckConstraint(
            "(satisfaction_score BETWEEN 1 AND 10) OR satisfaction_score IS NULL",
            name="ck_conversation_grades_satisfaction_score_range",
        ),
        sa.CheckConstraint(
            "(frustration_score BETWEEN 1 AND 10) OR frustration_score IS NULL",
            name="ck_conversation_grades_frustration_score_range",
        ),
        sa.CheckConstraint(
            "(escalation_type IN ('Natural', 'Failure', 'None')) OR escalation_type IS NULL",
            name="ck_conversation_grades_escalation_type_values",
        ),
    )

    op.create_index(
        "ix_conversation_grades_phone_number",
        "conversation_grades",
        ["phone_number"],
        unique=False,
    )
    op.create_index(
        "ix_conversation_grades_grade_date",
        "conversation_grades",
        ["grade_date"],
        unique=False,
    )
    op.create_index(
        "ix_conversation_grades_created_at",
        "conversation_grades",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "ix_conversation_grades_intent_label",
        "conversation_grades",
        ["intent_label"],
        unique=False,
    )


def downgrade() -> None:
    if _table_exists("conversation_grades"):
        op.drop_table("conversation_grades")
