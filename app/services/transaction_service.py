from sqlalchemy.orm import Session
from app.repositories import transaction_repository
from app.schemas.transaction import TransactionCreate, TransactionResponse, TransactionList


def create(db: Session, request: TransactionCreate) -> TransactionResponse:
    transaction_data = {
        "type": request.type,
        "amount": request.amount,
        "description": request.description,
        "reference": request.reference,
        "person_id": request.person_id,
        "created_by": 1  # TODO: Get from auth
    }
    
    transaction = transaction_repository.create(db, transaction_data)
    return transaction


def get_all(db: Session, page: int, limit: int, type: str = None, start_date: str = None, end_date: str = None) -> TransactionList:
    items, total = transaction_repository.get_all(db, page, limit, type)
    
    return TransactionList(
        items=items,
        total=total,
        page=page,
        limit=limit
    )


def get_by_id(db: Session, transaction_id: int) -> TransactionResponse:
    return transaction_repository.get_by_id(db, transaction_id)
