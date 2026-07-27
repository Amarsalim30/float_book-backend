"""
Ledger repository — all DB access for the LedgerEntry model.

Balances are ALWAYS derived from ledger sums, never from a stored running
total.  This is the architectural rule: the ledger is the source of truth.
"""
from decimal import Decimal
from typing import Literal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.ledger_entry import LedgerEntry

AccountType = Literal["cash", "float", "bank", "mpesa"]
EntryType = Literal["seed", "credit", "debit"]


def create_seed_entry(
    db: Session,
    business_id: int,
    account_type: AccountType,
    amount: Decimal,
    created_by: int,
    description: str | None = None,
) -> LedgerEntry:
    """Insert an opening seed entry for *account_type*.

    Does not commit — the caller owns the transaction boundary.
    """
    entry = LedgerEntry(
        business_id=business_id,
        account_type=account_type,
        entry_type="seed",
        amount=amount,
        description=description or f"Opening {account_type} balance",
        created_by=created_by,
    )
    db.add(entry)
    return entry


def create_entry(
    db: Session,
    business_id: int,
    account_type: AccountType,
    entry_type: EntryType,
    amount: Decimal,
    created_by: int,
    description: str | None = None,
    transaction_id: int | None = None,
) -> LedgerEntry:
    """Insert a credit or debit ledger entry.

    Does not commit — the caller owns the transaction boundary.
    """
    entry = LedgerEntry(
        business_id=business_id,
        account_type=account_type,
        entry_type=entry_type,
        amount=amount,
        description=description,
        transaction_id=transaction_id,
        created_by=created_by,
    )
    db.add(entry)
    return entry



def get_balance(db: Session, business_id: int, account_type: AccountType) -> Decimal:
    """Derive the current balance for *account_type* from the ledger.

    Balance = SUM(seed + credit amounts) - SUM(debit amounts).
    Returns Decimal("0") when no entries exist.
    """
    inflow = (
        db.query(func.coalesce(func.sum(LedgerEntry.amount), 0))
        .filter(
            LedgerEntry.business_id == business_id,
            LedgerEntry.account_type == account_type,
            LedgerEntry.entry_type.in_(["seed", "credit"]),
        )
        .scalar()
    )

    outflow = (
        db.query(func.coalesce(func.sum(LedgerEntry.amount), 0))
        .filter(
            LedgerEntry.business_id == business_id,
            LedgerEntry.account_type == account_type,
            LedgerEntry.entry_type == "debit",
        )
        .scalar()
    )

    return Decimal(str(inflow)) - Decimal(str(outflow))
