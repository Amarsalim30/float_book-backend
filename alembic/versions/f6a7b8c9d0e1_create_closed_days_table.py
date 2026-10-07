"""create_closed_days_table

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-10-07 22:36:00.000000

Adds closed_days table for daily reconciliation and close-day checkpoints.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "closed_days",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("business_id", sa.Integer(), nullable=False),
        sa.Column("closed_date", sa.Date(), nullable=False),
        sa.Column("opening_cash", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("expected_cash", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("actual_cash", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("cash_variance", sa.Numeric(precision=14, scale=2), nullable=False, server_default="0.00"),
        sa.Column("opening_float", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("expected_float", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("actual_float", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("float_variance", sa.Numeric(precision=14, scale=2), nullable=False, server_default="0.00"),
        sa.Column("status", sa.String(), nullable=False, server_default="balanced"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("post_adjustment", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("adjustment_transaction_id", sa.Integer(), nullable=True),
        sa.Column("closed_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"]),
        sa.ForeignKeyConstraint(["closed_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["adjustment_transaction_id"], ["transactions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("business_id", "closed_date", name="uq_closed_days_business_date"),
    )
    op.create_index(
        "ix_closed_days_business_date",
        "closed_days",
        ["business_id", "closed_date"],
    )
    op.create_index(
        "ix_closed_days_id",
        "closed_days",
        ["id"],
    )


def downgrade() -> None:
    op.drop_index("ix_closed_days_id", table_name="closed_days")
    op.drop_index("ix_closed_days_business_date", table_name="closed_days")
    op.drop_table("closed_days")
