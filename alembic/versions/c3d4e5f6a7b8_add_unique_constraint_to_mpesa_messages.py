"""add_unique_constraint_to_mpesa_messages

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-08-13 16:10:00.000000
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Clean up duplicate unattached mpesa_messages before creating unique constraint
    op.execute(
        sa.text(
            """
            DELETE FROM mpesa_messages
            WHERE transaction_id IS NULL
            AND id NOT IN (
                SELECT MIN(id)
                FROM mpesa_messages
                GROUP BY business_id, reference
            )
            """
        )
    )

    # 2. Add unique constraint on (business_id, reference)
    op.create_unique_constraint(
        "uq_mpesa_messages_business_reference",
        "mpesa_messages",
        ["business_id", "reference"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_mpesa_messages_business_reference",
        "mpesa_messages",
        type_="unique",
    )
