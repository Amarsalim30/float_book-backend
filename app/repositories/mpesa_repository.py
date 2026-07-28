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


def get_recent_unused_incoming(db: Session, business_id: int, limit: int = 20) -> list[MpesaMessage]:
    """Get recent unused incoming M-Pesa messages for a business."""
    return (
        db.query(MpesaMessage)
        .filter(
            MpesaMessage.business_id == business_id,
            MpesaMessage.direction == "MONEY_RECEIVED",
            MpesaMessage.transaction_id.is_(None),
        )
        .order_by(MpesaMessage.message_timestamp.desc())
        .limit(limit)
        .all()
    )
