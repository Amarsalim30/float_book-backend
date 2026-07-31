"""
Repository for TrackedAccount — all raw DB access.

Callers own the transaction boundary (no commit here).
"""
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.ledger_entry import LedgerEntry
from app.models.tracked_account import TrackedAccount


def create(db: Session, data: dict) -> TrackedAccount:
    account = TrackedAccount(**data)
    db.add(account)
    return account


def get_by_id(db: Session, business_id: int, account_id: int) -> TrackedAccount | None:
    return (
        db.query(TrackedAccount)
        .filter(
            TrackedAccount.id == account_id,
            TrackedAccount.business_id == business_id,
        )
        .first()
    )


def get_all(db: Session, business_id: int) -> list[TrackedAccount]:
    return (
        db.query(TrackedAccount)
        .filter(TrackedAccount.business_id == business_id)
        .order_by(TrackedAccount.name)
        .all()
    )


def get_balance(db: Session, business_id: int, account_id: int) -> Decimal:
    """
    Canonical balance calculation for a single TrackedAccount.

    Balance = SUM(credit entries) - SUM(debit entries)
    Always >= 0 in V1 (enforced in service layer before allowing debits).
    """
    credits = (
        db.query(func.coalesce(func.sum(LedgerEntry.amount), 0))
        .filter(
            LedgerEntry.business_id == business_id,
            LedgerEntry.tracked_account_id == account_id,
            LedgerEntry.entry_type == "credit",
        )
        .scalar()
    )
    debits = (
        db.query(func.coalesce(func.sum(LedgerEntry.amount), 0))
        .filter(
            LedgerEntry.business_id == business_id,
            LedgerEntry.tracked_account_id == account_id,
            LedgerEntry.entry_type == "debit",
        )
        .scalar()
    )
    return Decimal(str(credits)) - Decimal(str(debits))


def get_ledger_history(
    db: Session, business_id: int, account_id: int, limit: int = 50
) -> list[LedgerEntry]:
    """Return most-recent ledger entries for the account, newest first."""
    return (
        db.query(LedgerEntry)
        .filter(
            LedgerEntry.business_id == business_id,
            LedgerEntry.tracked_account_id == account_id,
        )
        .order_by(LedgerEntry.created_at.desc(), LedgerEntry.id.desc())
        .limit(limit)
        .all()
    )


def get_all_ledger_history_asc(
    db: Session, business_id: int, account_id: int
) -> list[LedgerEntry]:
    """Return all ledger entries for the account in deterministic chronological order."""
    return (
        db.query(LedgerEntry)
        .filter(
            LedgerEntry.business_id == business_id,
            LedgerEntry.tracked_account_id == account_id,
        )
        .order_by(LedgerEntry.created_at.asc(), LedgerEntry.id.asc())
        .all()
    )

