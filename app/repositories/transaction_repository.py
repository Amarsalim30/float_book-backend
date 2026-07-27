from datetime import datetime
from zoneinfo import ZoneInfo
from sqlalchemy.orm import Session
from app.models.transaction import Transaction

NAIROBI_TZ = ZoneInfo("Africa/Nairobi")


def create(db: Session, transaction_data: dict) -> Transaction:
    """Create a transaction object without committing so the caller controls the transaction boundary."""
    transaction = Transaction(**transaction_data)
    db.add(transaction)
    db.flush()
    return transaction


def get_by_id(db: Session, transaction_id: int) -> Transaction | None:
    return db.query(Transaction).filter(Transaction.id == transaction_id).first()


def get_all(
    db: Session, business_id: int, page: int = 1, limit: int = 20, type: str | None = None
) -> tuple[list[Transaction], int]:
    query = db.query(Transaction).filter(Transaction.business_id == business_id)

    if type:
        query = query.filter(Transaction.type == type)

    total = query.count()
    items = (
        query.order_by(Transaction.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    return items, total


def get_today_by_business(
    db: Session, business_id: int, limit: int = 10
) -> list[Transaction]:
    """Return today's transactions for the business based on Nairobi timezone."""
    now_nairobi = datetime.now(NAIROBI_TZ)
    day_start = now_nairobi.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = now_nairobi.replace(hour=23, minute=59, second=59, microsecond=999999)

    return (
        db.query(Transaction)
        .filter(
            Transaction.business_id == business_id,
            Transaction.created_at >= day_start,
            Transaction.created_at <= day_end,
        )
        .order_by(Transaction.created_at.desc())
        .limit(limit)
        .all()
    )
