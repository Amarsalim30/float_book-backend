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
            WHERE id IN (
                SELECT m.id
                FROM mpesa_messages m
                WHERE m.transaction_id IS NULL
                AND EXISTS (
                    SELECT 1 FROM mpesa_messages m2
                    WHERE m2.business_id = m.business_id
                    AND m2.reference = m.reference
                    AND (
                        m2.transaction_id IS NOT NULL
                        OR m2.id < m.id
                    )
                )
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
