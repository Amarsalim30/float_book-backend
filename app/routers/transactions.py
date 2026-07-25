from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas.transaction import TransactionCreate, TransactionResponse, TransactionList
from app.services import transaction_service

router = APIRouter(prefix="/transactions", tags=["Transactions"])


@router.post("/", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
def create_transaction(request: TransactionCreate, db: Session = Depends(get_db)):
    return transaction_service.create(db, request)


@router.get("/", response_model=TransactionList)
def get_transactions(
    page: int = 1,
    limit: int = 20,
    type: str = None,
    start_date: str = None,
    end_date: str = None,
    db: Session = Depends(get_db)
):
    return transaction_service.get_all(db, page, limit, type, start_date, end_date)


@router.get("/{id}", response_model=TransactionResponse)
def get_transaction(id: int, db: Session = Depends(get_db)):
    transaction = transaction_service.get_by_id(db, id)
    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found"
        )
    return transaction
