from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.user import User
from app.repositories import business_repository, closed_day_repository, ledger_repository, mpesa_repository, transaction_repository
from app.schemas.dashboard import ActivityItem, DashboardResponse, LedgerEffect

NAIROBI_TZ = ZoneInfo("Africa/Nairobi")


def get_dashboard(db: Session, current_user: User) -> DashboardResponse:
    business = business_repository.get_by_owner(db, current_user.id)
    if not business:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business not found. Complete onboarding first.",
        )

    cash_balance = ledger_repository.get_balance(db, business.id, "cash")
    float_balance = ledger_repository.get_balance(db, business.id, "float")

    today_txns = transaction_repository.get_today_by_business(db, business.id, limit=10)

    # Check if today is already closed
    today_date = datetime.now(NAIROBI_TZ).date()
    closed_today = closed_day_repository.get_by_date(db, business.id, today_date)

    activity_items = [
        ActivityItem(
            id=tx.id,
            type=tx.type,
            description=tx.description,
            amount=tx.amount,
            created_at=tx.created_at,
            direction=_activity_direction(tx),
            counterparty_name=_activity_counterparty(tx),
            effects=[
                LedgerEffect(
                    account_type=le.account_type,
                    direction=le.entry_type,
                    amount=le.amount,
                    tracked_account_name=(
                        le.tracked_account.name if le.tracked_account else None
                    ),
                )
                for le in tx.ledger_entries
            ],
        )
        for tx in today_txns
    ]

    unrecorded_msgs = mpesa_repository.get_recent_unused(db, business.id)
    unrecorded_count = len(unrecorded_msgs)
    unrecorded_total = sum((Decimal(str(m.amount)) for m in unrecorded_msgs), Decimal("0.00"))

    return DashboardResponse(
        business_name=business.business_name,
        cash_balance=cash_balance,
        float_balance=float_balance,
        today_activity=activity_items,
        day_closed=closed_today is not None,
        day_status=closed_today.status if closed_today else None,
        closing_variance=(
            (closed_today.cash_variance + closed_today.float_variance)
            if closed_today
            else None
        ),
        closing_cash_variance=closed_today.cash_variance if closed_today else None,
        closing_float_variance=closed_today.float_variance if closed_today else None,
        unrecorded_mpesa_count=unrecorded_count,
        unrecorded_mpesa_total=unrecorded_total,
    )


def _activity_direction(tx) -> str:
    """Direction relative to the business's operational (cash/float) accounts.

    Money moving out of operational accounts = "out"; money moving in = "in".
    For transfers this cleanly separates Give/Return (out) from Get-Back/Receive (in).
    """
    op_credits = sum(
        le.amount
        for le in tx.ledger_entries
        if le.account_type in ("cash", "float")
        and le.entry_type in ("seed", "credit")
    )
    op_debits = sum(
        le.amount
        for le in tx.ledger_entries
        if le.account_type in ("cash", "float") and le.entry_type == "debit"
    )
    return "out" if op_debits > op_credits else "in"


def _activity_counterparty(tx) -> str | None:
    """The other party involved in a transaction.

    Transfers always target a tracked account; sales/expenses may reference a person.
    """
    for le in tx.ledger_entries:
        if le.account_type == "tracked" and le.tracked_account:
            return le.tracked_account.name
    if tx.person:
        return tx.person.name
    return None
