from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.ledger import LedgerStatementResponse
from app.services import ledger_service

router = APIRouter(prefix="/ledger", tags=["Ledger"])


@router.get("/{account_type}", response_model=LedgerStatementResponse)
def get_ledger_statement(
    account_type: str,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ledger_service.get_statement(
        db, current_user, account_type=account_type, page=page, limit=limit
    )
