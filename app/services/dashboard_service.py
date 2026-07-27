from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.user import User
from app.repositories import business_repository, ledger_repository, transaction_repository
from app.schemas.dashboard import ActivityItem, DashboardResponse, LedgerEffect


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

    activity_items = [
        ActivityItem(
            id=tx.id,
            type=tx.type,
            description=tx.description,
            amount=tx.amount,
            created_at=tx.created_at,
            effects=[
                LedgerEffect(
                    account_type=le.account_type,
                    direction=le.entry_type,
                    amount=le.amount,
                )
                for le in tx.ledger_entries
            ],
        )
        for tx in today_txns
    ]

    return DashboardResponse(
        business_name=business.business_name,
        cash_balance=cash_balance,
        float_balance=float_balance,
        today_activity=activity_items,
        day_closed=False,
        closing_variance=None,
    )
