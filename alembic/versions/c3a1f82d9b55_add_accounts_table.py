"""add_accounts_table

Revision ID: c3a1f82d9b55
Revises: 92a4f0787d6d
Create Date: 2026-03-04 12:40:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "c3a1f82d9b55"
down_revision: Union[str, Sequence[str], None] = "92a4f0787d6d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return table_name in inspector.get_table_names()


def _index_exists(table_name: str, index_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(index["name"] == index_name for index in inspector.get_indexes(table_name))


def upgrade() -> None:
    if not _table_exists("accounts"):
        op.create_table(
            "accounts",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("email", sa.String(length=320), nullable=False),
            sa.Column("password_hash", sa.String(length=255), nullable=False),
            sa.Column("full_name", sa.String(length=150), nullable=False),
            sa.Column("role", sa.String(length=32), nullable=False),
            sa.Column(
                "is_active",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("true"),
            ),
            sa.Column("last_login_at", sa.DateTime(timezone=False), nullable=True),
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
                "role IN ('super_admin', 'company_admin', 'analyst')",
                name="ck_accounts_role_values",
            ),
            sa.CheckConstraint(
                "length(trim(password_hash)) > 0",
                name="ck_accounts_password_hash_non_empty",
            ),
            sa.CheckConstraint(
                "length(trim(full_name)) > 0",
                name="ck_accounts_full_name_non_empty",
            ),
            sa.PrimaryKeyConstraint("id", name="pk_accounts"),
        )

    if not _index_exists("accounts", "uq_accounts_email_lower"):
        op.create_index(
            "uq_accounts_email_lower",
            "accounts",
            [sa.text("lower(email)")],
            unique=True,
        )
    if not _index_exists("accounts", "ix_accounts_role"):
        op.create_index("ix_accounts_role", "accounts", ["role"], unique=False)
    if not _index_exists("accounts", "ix_accounts_is_active"):
        op.create_index("ix_accounts_is_active", "accounts", ["is_active"], unique=False)


def downgrade() -> None:
    if not _table_exists("accounts"):
        return

    if _index_exists("accounts", "ix_accounts_is_active"):
        op.drop_index("ix_accounts_is_active", table_name="accounts")
    if _index_exists("accounts", "ix_accounts_role"):
        op.drop_index("ix_accounts_role", table_name="accounts")
    if _index_exists("accounts", "uq_accounts_email_lower"):
        op.drop_index("uq_accounts_email_lower", table_name="accounts")

    op.drop_table("accounts")

