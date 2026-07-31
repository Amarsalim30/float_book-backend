"""add_dual_position_accounts_to_people

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-07-31 22:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add person_id and position_type to tracked_accounts
    op.add_column(
        "tracked_accounts",
        sa.Column("person_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "tracked_accounts",
        sa.Column("position_type", sa.String(), nullable=False, server_default="tracked"),
    )
    op.create_foreign_key(
        "fk_tracked_accounts_person_id",
        "tracked_accounts",
        "people",
        ["person_id"],
        ["id"],
    )
    op.create_index(
        op.f("ix_tracked_accounts_person_id"),
        "tracked_accounts",
        ["person_id"],
        unique=False,
    )
    op.create_unique_constraint(
        "uq_person_position",
        "tracked_accounts",
        ["person_id", "position_type"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_person_position", "tracked_accounts", type_="unique")
    op.drop_index(op.f("ix_tracked_accounts_person_id"), table_name="tracked_accounts")
    op.drop_constraint("fk_tracked_accounts_person_id", "tracked_accounts", type_="foreignkey")
    op.drop_column("tracked_accounts", "position_type")
    op.drop_column("tracked_accounts", "person_id")
