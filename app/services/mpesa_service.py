from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.user import User
from app.repositories import business_repository, mpesa_repository
from app.schemas.mpesa import MpesaMessageCreate, MpesaMessageResponse


def create_message(
    db: Session, current_user: User, request: MpesaMessageCreate
) -> MpesaMessageResponse:
    business = business_repository.get_by_owner(db, current_user.id)
    if not business:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business not found. Complete onboarding first.",
        )

    message_data = {
        "business_id": business.id,
        "reference": request.reference,
        "sender": request.sender,
        "amount": request.amount,
        "direction": request.direction,
        "raw_text": request.raw_text,
        "message_timestamp": request.message_timestamp,
    }

    try:
        message = mpesa_repository.create(db, message_data)
        db.commit()
        db.refresh(message)
        return MpesaMessageResponse.model_validate(message)
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to ingest M-Pesa message: {exc}",
        ) from exc


def get_recent_messages(
    db: Session,
    current_user: User,
    direction: str = "MONEY_RECEIVED",
    unused: bool = True,
    limit: int = 20,
) -> list[MpesaMessageResponse]:
    business = business_repository.get_by_owner(db, current_user.id)
    if not business:
        return []

    if direction == "MONEY_RECEIVED" and unused:
        messages = mpesa_repository.get_recent_unused_incoming(
            db, business_id=business.id, limit=limit
        )
    else:
        messages = []

    return [MpesaMessageResponse.model_validate(msg) for msg in messages]
