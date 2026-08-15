"""fix_mpesa_message_directions

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-08-15 10:30:00.000000

Corrects the M-Pesa message direction column that was stored inverted by an
older phone build. Convention (agent float perspective):
  Take = money OUT of the float  -> MONEY_SENT
  Give = money INTO the float    -> MONEY_RECEIVED

Older builds ingested Give as MONEY_SENT and Take as MONEY_RECEIVED. This only
touches rows whose stored direction contradicts the raw SMS text, so it is a
no-op for data already stored correctly.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE mpesa_messages
            SET direction = CASE
                WHEN raw_text ILIKE '%Give%' THEN 'MONEY_RECEIVED'
                WHEN raw_text ILIKE '%Take%' THEN 'MONEY_SENT'
                ELSE direction
            END
            WHERE (raw_text ILIKE '%Give%' AND direction = 'MONEY_SENT')
               OR (raw_text ILIKE '%Take%' AND direction = 'MONEY_RECEIVED')
            """
        )
    )


def downgrade() -> None:
    # The old inverted state is indistinguishable from the 5 legitimately
    # correct rows, so the correction is not reversible.
    pass
