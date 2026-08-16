"""add_composite_indexes_for_scaling

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-08-16 13:30:00.000000

Adds composite indexes for the two query patterns that grow with a
business's accumulated transaction history (10-year horizon):

  * Balance sums (`get_balance`) read by (business_id, account_type,
    entry_type)  -> ix_ledger_entries_business_type_entry
  * Ledger statement ORDER BY (business_id, account_type, created_at, id)
    -> ix_ledger_entries_business_type_created
  * Recent-transaction listing ORDER BY (business_id, created_at, id)
    -> ix_transactions_business_created

Without these, Postgres rescans/sorts each business's full history on
every dashboard and statement load. With them, each query is a bounded
index-range scan that stays fast regardless of history size.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_ledger_entries_business_type_entry",
        "ledger_entries",
        ["business_id", "account_type", "entry_type"],
    )
    op.create_index(
        "ix_ledger_entries_business_type_created",
        "ledger_entries",
        ["business_id", "account_type", "created_at", "id"],
    )
    op.create_index(
        "ix_transactions_business_created",
        "transactions",
        ["business_id", "created_at", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_transactions_business_created", table_name="transactions")
    op.drop_index("ix_ledger_entries_business_type_created", table_name="ledger_entries")
    op.drop_index("ix_ledger_entries_business_type_entry", table_name="ledger_entries")
