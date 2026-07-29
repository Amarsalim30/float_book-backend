"""create_tracked_accounts

Revision ID: a1b2c3d4e5f6
Revises: 3c98183be872
Create Date: 2026-07-29 01:15:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "3c98183be872"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create tracked_accounts table
    op.create_table(
        "tracked_accounts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("business_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("account_type", sa.String(), nullable=False, server_default="person"),
        sa.Column("phone", sa.String(), nullable=True),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_tracked_accounts_id"), "tracked_accounts", ["id"], unique=False
    )
    op.create_index(
        op.f("ix_tracked_accounts_business_id"),
        "tracked_accounts",
        ["business_id"],
        unique=False,
    )

    # 2. Add tracked_account_id FK to ledger_entries
    op.add_column(
        "ledger_entries",
        sa.Column("tracked_account_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_ledger_entries_tracked_account_id",
        "ledger_entries",
        "tracked_accounts",
        ["tracked_account_id"],
        ["id"],
    )
    op.create_index(
        op.f("ix_ledger_entries_tracked_account_id"),
        "ledger_entries",
        ["tracked_account_id"],
        unique=False,
    )


def downgrade() -> None:
    # Remove tracked_account_id from ledger_entries
    op.drop_index(
        op.f("ix_ledger_entries_tracked_account_id"), table_name="ledger_entries"
    )
    op.drop_constraint(
        "fk_ledger_entries_tracked_account_id", "ledger_entries", type_="foreignkey"
    )
    op.drop_column("ledger_entries", "tracked_account_id")

    # Drop tracked_accounts table
    op.drop_index(
        op.f("ix_tracked_accounts_business_id"), table_name="tracked_accounts"
    )
    op.drop_index(op.f("ix_tracked_accounts_id"), table_name="tracked_accounts")
    op.drop_table("tracked_accounts")
