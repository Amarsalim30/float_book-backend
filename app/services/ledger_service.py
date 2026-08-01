from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.user import User
from app.repositories import business_repository, ledger_repository
from app.schemas.ledger import LedgerStatementResponse


def get_statement(
    db: Session,
    current_user: User,
    account_type: str,
    page: int = 1,
    limit: int = 20,
) -> LedgerStatementResponse:
    business = business_repository.get_by_owner(db, current_user.id)
    if not business:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business not found. Complete onboarding first.",
        )

    statement_data = ledger_repository.get_ledger_statement(
        db, business_id=business.id, account_type=account_type.lower(), page=page, limit=limit
    )

    return LedgerStatementResponse(**statement_data)
