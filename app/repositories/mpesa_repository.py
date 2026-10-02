from sqlalchemy.orm import Session
from app.models.mpesa_message import MpesaMessage


def create(db: Session, message_data: dict) -> MpesaMessage:
    """Create an MpesaMessage object without committing so caller controls transaction boundary."""
    message = MpesaMessage(**message_data)
    db.add(message)
    db.flush()
    return message


def get_by_id(db: Session, message_id: int) -> MpesaMessage | None:
    return db.query(MpesaMessage).filter(MpesaMessage.id == message_id).first()


def get_by_reference(
    db: Session, business_id: int, reference: str
) -> MpesaMessage | None:
    """Find an existing message by reference for a business (idempotency check)."""
    return (
        db.query(MpesaMessage)
        .filter(
            MpesaMessage.business_id == business_id,
            MpesaMessage.reference == reference,
        )
        .first()
    )


def get_messages(
    db: Session,
    business_id: int,
    direction: str | None = None,
    unused: bool | None = True,
    limit: int | None = None,
) -> list[MpesaMessage]:
    """Query M-Pesa messages for a business with optional direction, unused filter, and limit."""
    # ponytail: unified query with no artificial hard cap
    query = db.query(MpesaMessage).filter(MpesaMessage.business_id == business_id)
    if direction is not None:
        query = query.filter(MpesaMessage.direction == direction)
    if unused is True:
        query = query.filter(MpesaMessage.transaction_id.is_(None))
    elif unused is False:
        query = query.filter(MpesaMessage.transaction_id.is_not(None))
    query = query.order_by(MpesaMessage.message_timestamp.desc())
    if limit is not None:
        query = query.limit(limit)
    return query.all()


def get_recent_unused(
    db: Session, business_id: int, direction: str | None = None, limit: int | None = None
) -> list[MpesaMessage]:
    """Get recent unused M-Pesa messages of *direction* for a business."""
    return get_messages(db, business_id=business_id, direction=direction, unused=True, limit=limit)


def get_recent_unused_incoming(db: Session, business_id: int, limit: int | None = None) -> list[MpesaMessage]:
    """Get recent unused incoming M-Pesa messages for a business."""
    return get_messages(
        db, business_id=business_id, direction="MONEY_RECEIVED", unused=True, limit=limit
    )


def delete_unused_older_than(db: Session, cutoff) -> int:
    """Delete unused (never attached to a transaction) messages older than cutoff."""
    return (
        db.query(MpesaMessage)
        .filter(
            MpesaMessage.transaction_id.is_(None),
            MpesaMessage.message_timestamp < cutoff,
        )
        .delete(synchronize_session=False)
    )
