from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.transaction import Transaction


def create(db: Session, transaction_data: dict):
    transaction = Transaction(**transaction_data)
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    return transaction


def get_by_id(db: Session, transaction_id: int):
    return db.query(Transaction).filter(Transaction.id == transaction_id).first()


def get_all(db: Session, page: int = 1, limit: int = 20, type: str = None):
    query = db.query(Transaction)
    
    if type:
        query = query.filter(Transaction.type == type)
    
    total = query.count()
    items = query.order_by(Transaction.created_at.desc()).offset((page - 1) * limit).limit(limit).all()
    
    return items, total
