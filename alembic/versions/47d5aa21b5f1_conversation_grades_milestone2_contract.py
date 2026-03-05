"""conversation_grades_milestone2_contract

Revision ID: 47d5aa21b5f1
Revises: 8c17673a6641
Create Date: 2026-03-02 09:15:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "47d5aa21b5f1"
down_revision: Union[str, Sequence[str], None] = "8c17673a6641"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "conversation_grades",
        sa.Column("identity_type", sa.String(length=16), nullable=True),
    )
    op.add_column(
        "conversation_grades",
        sa.Column("conversation_identity", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "conversation_grades",
        sa.Column("intent_code", sa.String(length=32), nullable=True),
    )

    op.create_index(
        "ix_conversation_grades_identity_type",
        "conversation_grades",
        ["identity_type"],
        unique=False,
    )
    op.create_index(
        "ix_conversation_grades_conversation_identity",
        "conversation_grades",
        ["conversation_identity"],
        unique=False,
    )
    op.create_index(
        "ix_conversation_grades_intent_code",
        "conversation_grades",
        ["intent_code"],
        unique=False,
    )

    op.execute("""
        UPDATE conversation_grades
        SET identity_type = 'phone',
            conversation_identity = phone_number
        WHERE identity_type IS NULL AND conversation_identity IS NULL
    """)


def downgrade() -> None:
    op.drop_index(
        "ix_conversation_grades_intent_code", table_name="conversation_grades"
    )
    op.drop_index(
        "ix_conversation_grades_conversation_identity", table_name="conversation_grades"
    )
    op.drop_index(
        "ix_conversation_grades_identity_type", table_name="conversation_grades"
    )

    op.drop_column("conversation_grades", "intent_code")
    op.drop_column("conversation_grades", "conversation_identity")
    op.drop_column("conversation_grades", "identity_type")
