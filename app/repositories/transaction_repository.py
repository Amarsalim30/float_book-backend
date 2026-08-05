from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from sqlalchemy import or_, cast, String
from sqlalchemy.orm import Session
from app.models.transaction import Transaction
from app.models.person import Person
from app.models.mpesa_message import MpesaMessage
from app.models.ledger_entry import LedgerEntry

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
    db: Session,
    business_id: int,
    page: int = 1,
    limit: int = 20,
    type: str | None = None,
    q: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    sort: str = "desc",
) -> tuple[list[Transaction], int]:
    query = (
        db.query(Transaction)
        .outerjoin(Person, Transaction.person_id == Person.id)
        .outerjoin(MpesaMessage, Transaction.id == MpesaMessage.transaction_id)
        .filter(Transaction.business_id == business_id)
    )

    if type:
        query = query.filter(Transaction.type == type)

    if date_from:
        query = query.filter(Transaction.created_at >= date_from)

    if date_to:
        query = query.filter(Transaction.created_at <= date_to)

    if q and q.strip():
        search_term = f"%{q.strip()}%"
        query = query.filter(
            or_(
                Transaction.reference.ilike(search_term),
                Transaction.description.ilike(search_term),
                Transaction.type.ilike(search_term),
                cast(Transaction.amount, String).ilike(search_term),
                Person.name.ilike(search_term),
                Person.phone.ilike(search_term),
                MpesaMessage.reference.ilike(search_term),
                MpesaMessage.sender.ilike(search_term),
                MpesaMessage.raw_text.ilike(search_term),
            )
        )

    # Distinct items in case outer joins create duplicates
    query = query.distinct()

    total = query.count()

    order_col = Transaction.created_at.asc() if sort == "asc" else Transaction.created_at.desc()
    items = (
        query.order_by(order_col)
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
    day_start_nairobi = now_nairobi.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end_nairobi = now_nairobi.replace(hour=23, minute=59, second=59, microsecond=999999)

    # created_at is stored in UTC (func.now()), so the Nairobi "today" window
    # must be converted to UTC before comparison. Comparing Nairobi-aware
    # bounds against UTC values breaks string-based comparisons in SQLite and
    # silently shifts the window by the UTC+3 offset.
    day_start = day_start_nairobi.astimezone(timezone.utc)
    day_end = day_end_nairobi.astimezone(timezone.utc)

    return (
        db.query(Transaction)
        .filter(
            Transaction.business_id == business_id,
            Transaction.created_at >= day_start,
            Transaction.created_at <= day_end,
        )
        .order_by(Transaction.created_at.desc(), Transaction.id.desc())
        .limit(limit)
        .all()
    )
