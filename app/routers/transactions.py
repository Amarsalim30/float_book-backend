from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.transaction import TransactionCreate, TransactionList, TransactionResponse
from app.services import transaction_service

router = APIRouter(prefix="/transactions", tags=["Transactions"])


@router.post("/", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
def create_transaction(
    request: TransactionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return transaction_service.create(db, current_user, request)


@router.get("/", response_model=TransactionList)
def get_transactions(
    page: int = 1,
    limit: int = 20,
    type: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return transaction_service.get_all(db, current_user, page=page, limit=limit, type=type)


@router.get("/{id}", response_model=TransactionResponse)
def get_transaction(
    id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return transaction_service.get_by_id(db, current_user, id)
