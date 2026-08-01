"""
Ledger repository — all DB access for the LedgerEntry model.

Balances are ALWAYS derived from ledger sums, never from a stored running
total.  This is the architectural rule: the ledger is the source of truth.
"""
from datetime import datetime
from decimal import Decimal
from typing import Literal
from zoneinfo import ZoneInfo

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.ledger_entry import LedgerEntry
from app.models.transaction import Transaction

AccountType = Literal["cash", "float", "bank", "mpesa"]
EntryType = Literal["seed", "credit", "debit"]
NAIROBI_TZ = ZoneInfo("Africa/Nairobi")


def create_seed_entry(
    db: Session,
    business_id: int,
    account_type: AccountType,
    amount: Decimal,
    created_by: int,
    description: str | None = None,
) -> LedgerEntry:
    """Insert an opening seed entry for *account_type*."""
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
    """Insert a credit or debit ledger entry."""
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


def get_balance(db: Session, business_id: int, account_type: str) -> Decimal:
    """Derive the current balance for *account_type* from the ledger."""
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


def get_ledger_statement(
    db: Session,
    business_id: int,
    account_type: str,
    page: int = 1,
    limit: int = 20,
) -> dict:
    """Fetch all ledger entries for account_type, compute running balance chronologically,

    and return statement response dict with totals and pagination metadata (newest first).
    """
    entries = (
        db.query(LedgerEntry)
        .filter(
            LedgerEntry.business_id == business_id,
            LedgerEntry.account_type == account_type,
        )
        .order_by(LedgerEntry.created_at.asc(), LedgerEntry.id.asc())
        .all()
    )

    now_nairobi = datetime.now(NAIROBI_TZ)
    day_start = now_nairobi.replace(hour=0, minute=0, second=0, microsecond=0)

    running_bal = Decimal("0.00")
    total_credits = Decimal("0.00")
    total_debits = Decimal("0.00")
    today_net = Decimal("0.00")

    statement_rows = []

    for entry in entries:
        amt = Decimal(str(entry.amount))
        debit_amt = None
        credit_amt = None

        created_dt = entry.created_at
        if created_dt and created_dt.tzinfo is None:
            created_dt = created_dt.replace(tzinfo=NAIROBI_TZ)

        if entry.entry_type in ("seed", "credit"):
            running_bal += amt
            credit_amt = amt
            total_credits += amt
            if created_dt and created_dt >= day_start:
                today_net += amt
        elif entry.entry_type == "debit":
            running_bal -= amt
            debit_amt = amt
            total_debits += amt
            if created_dt and created_dt >= day_start:
                today_net -= amt

        tx_type = entry.transaction.type if entry.transaction else None
        ref = entry.transaction.reference if entry.transaction else None

        statement_rows.append(
            {
                "id": entry.id,
                "created_at": entry.created_at,
                "account_type": entry.account_type,
                "entry_type": entry.entry_type,
                "amount": amt,
                "debit_amount": debit_amt,
                "credit_amount": credit_amt,
                "running_balance": running_bal,
                "transaction_id": entry.transaction_id,
                "transaction_type": tx_type,
                "description": entry.description,
                "reference": ref,
            }
        )

    # Reverse list so newest entries are first
    statement_rows.reverse()
    total = len(statement_rows)
    total_pages = (total + limit - 1) // limit if limit > 0 else 1
    offset = (page - 1) * limit
    paginated_items = statement_rows[offset : offset + limit]

    return {
        "account_type": account_type,
        "current_balance": running_bal,
        "total_credits": total_credits,
        "total_debits": total_debits,
        "today_net": today_net,
        "items": paginated_items,
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_previous": page > 1,
    }
