"""
LedgerEntry model — the single source of truth for all account balances.

Every monetary movement in the system creates a LedgerEntry.  Balances are
derived by summing entries, never stored as a running total elsewhere.

Account types (MVP):
  cash   — physical cash in the drawer
  float  — mobile money float (M-Pesa, Airtel, etc.)

Entry types:
  seed   — written once at onboarding to establish the opening state
  credit — money coming in  (increases balance)
  debit  — money going out (decreases balance)

Derived balance for an account:
  SUM(amount) WHERE entry_type IN ('seed', 'credit')
  - SUM(amount) WHERE entry_type = 'debit'
"""
from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"

    __table_args__ = (
        Index(
            "ix_ledger_entries_business_type_entry",
            "business_id",
            "account_type",
            "entry_type",
        ),
        Index(
            "ix_ledger_entries_business_type_created",
            "business_id",
            "account_type",
            "created_at",
            "id",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)

    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False, index=True)

    # "cash" | "float" | "tracked"
    # Invariant: account_type="tracked" → tracked_account_id MUST be set
    #            account_type="cash"|"float" → tracked_account_id MUST be NULL
    account_type = Column(String, nullable=False)

    # "seed" | "credit" | "debit"
    entry_type = Column(String, nullable=False)

    # Always positive; direction is determined by entry_type
    amount = Column(Numeric(14, 2), nullable=False)

    description = Column(String, nullable=True)

    # Optional FK to transactions.id — links a ledger entry to its source
    transaction_id = Column(Integer, ForeignKey("transactions.id"), nullable=True, index=True)

    # Optional FK to tracked_accounts.id — set only when account_type="tracked"
    tracked_account_id = Column(
        Integer, ForeignKey("tracked_accounts.id"), nullable=True, index=True
    )

    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    business = relationship("Business", back_populates="ledger_entries")
    transaction = relationship("Transaction", back_populates="ledger_entries")
    tracked_account = relationship("TrackedAccount", back_populates="ledger_entries")
    creator = relationship("User", foreign_keys=[created_by])

